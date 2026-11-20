import datetime, io, pikepdf
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from reportlab.pdfgen import canvas
from pyhanko.sign import signers, fields
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

# 1. certificat de test (CA + semnatar), ca un certificat calificat simulat
now=datetime.datetime.now(datetime.timezone.utc)
def cert(subj, key, issuer, ikey, ca):
    b=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,subj)]))
       .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,issuer)])).public_key(key.public_key())
       .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=365))
       .add_extension(x509.BasicConstraints(ca=ca,path_length=None),critical=True))
    if not ca: b=b.add_extension(x509.KeyUsage(True,True,False,False,False,False,False,False,False),critical=True)
    else: b=b.add_extension(x509.KeyUsage(True,False,False,False,False,True,True,False,False),critical=True)
    return b.sign(ikey,hashes.SHA256())
cak=rsa.generate_private_key(public_exponent=65537,key_size=2048); ca=cert("CA test","" or cak,"CA test",cak,True)
k=rsa.generate_private_key(public_exponent=65537,key_size=2048); c=cert("Ion Popescu",k,"CA test",cak,False)
Path("key.pem").write_bytes(k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
Path("cert.pem").write_bytes(c.public_bytes(serialization.Encoding.PEM)); Path("ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
signer=signers.SimpleSigner.load("key.pem","cert.pem",ca_chain_files=("ca.pem",))
from pyhanko.keys import load_cert_from_pemder
vc=ValidationContext(trust_roots=[load_cert_from_pemder("ca.pem")])

# 2. doua documente semnate
def make(name,title):
    b=io.BytesIO(); cv=canvas.Canvas(b); cv.drawString(72,760,title); cv.drawString(72,740,"Document semnat electronic - test"); cv.save()
    w=IncrementalPdfFileWriter(io.BytesIO(b.getvalue()))
    out=signers.sign_pdf(w,signers.PdfSignatureMetadata(field_name="Semnatura"),signer=signer)
    Path(name).write_bytes(out.getvalue())
make("contract.pdf","Contract de finantare nr. 123"); make("act_aditional.pdf","Act aditional nr. 1")

def check(data,label):
    r=PdfFileReader(io.BytesIO(data)); sigs=r.embedded_signatures
    if not sigs: print(f"  {label}: NICIO semnatura"); return
    for s in sigs:
        st=validate_pdf_signature(s,vc)
        print(f"  {label}: intact={st.intact} valid={st.valid} acopera_tot={st.coverage.name}")

print("Originale:")
for f in ("contract.pdf","act_aditional.pdf"): check(Path(f).read_bytes(),f)

# 3. unire clasica (pagini lipite)
m=pikepdf.new()
for f in ("contract.pdf","act_aditional.pdf"): m.pages.extend(pikepdf.open(f).pages)
m.save("unire_clasica.pdf"); print("Unire clasica (pagini alipite):"); check(Path("unire_clasica.pdf").read_bytes(),"unire_clasica.pdf")

# 4. portofoliu: originalele incorporate neschimbate
p=pikepdf.new(); p.add_blank_page(page_size=(595,842))
for f in ("contract.pdf","act_aditional.pdf"):
    p.attachments[f]=pikepdf.AttachedFileSpec.from_filepath(p,Path(f))
p.Root.Collection=pikepdf.Dictionary(Type=pikepdf.Name.Collection,View=pikepdf.Name.D)
p.save("dosar_portofoliu.pdf")
print("Portofoliu (originale incorporate):")
q=pikepdf.open("dosar_portofoliu.pdf")
for name,spec in q.attachments.items():
    data=spec.get_file().read_bytes()
    print(f"  {name}: identic byte cu byte cu originalul = {data==Path(name).read_bytes()}")
    check(data,name+" extras")
