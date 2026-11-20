import io, hashlib, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import pikepdf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.keys import load_cert_from_pemder
from pyhanko_certvalidator import ValidationContext
vc=ValidationContext(trust_roots=[load_cert_from_pemder("ca.pem")])
signer=signers.SimpleSigner.load("key.pem","cert.pem",ca_chain_files=("ca.pem",))
files=["contract.pdf","act_aditional.pdf"]
info=[]
for f in files:
    d=Path(f).read_bytes(); r=PdfFileReader(io.BytesIO(d)); s=r.embedded_signatures[0]; st=validate_pdf_signature(s,vc)
    info.append((f,st.signing_cert.subject.human_friendly,str(st.signer_reported_dt)[:19],"VALIDA" if st.valid and st.intact else "INVALIDA",hashlib.sha256(d).hexdigest()[:16]))
# cuprins
b=io.BytesIO(); c=canvas.Canvas(b,pagesize=A4); c.setFont("Helvetica-Bold",14); c.drawString(60,780,"Dosar - cuprins si raport de semnaturi")
c.setFont("Helvetica",9); y=750
for i,(f,who,dt,stt,h) in enumerate(info,1):
    c.drawString(60,y,f"{i}. {f}  |  semnat: {who}  |  {dt}  |  semnatura: {stt}  |  SHA-256: {h}..."); y-=18
c.drawString(60,y-10,"Paginile urmatoare sunt copii de citire. Originalele semnate sunt atasate neschimbate in acest fisier."); c.save()
out=pikepdf.open(io.BytesIO(b.getvalue()))
for f in files:
    src=pikepdf.open(f)
    for pg in src.pages: out.pages.append(pg)
# eticheta pe copii
for i,pg in enumerate(out.pages[1:],1):
    lb=io.BytesIO(); c=canvas.Canvas(lb,pagesize=A4); c.setFont("Helvetica",8); c.setFillGray(0.4)
    c.drawString(40,20,"COPIE DE CITIRE - semnatura nu e valida pe aceasta pagina; originalul semnat este atasat"); c.save()
    lp=pikepdf.open(io.BytesIO(lb.getvalue())); out.pages.append(lp.pages[0]); ov=out.pages[-1]; pg.add_overlay(ov); del out.pages[-1]
    if "/Annots" in pg: del pg["/Annots"]
for f in files: out.attachments[f]=pikepdf.AttachedFileSpec.from_filepath(out,Path(f))
out.save("tmp3.pdf")
w=IncrementalPdfFileWriter(io.BytesIO(Path("tmp3.pdf").read_bytes()))
o=signers.sign_pdf(w,signers.PdfSignatureMetadata(field_name="SigiliuDosar"),signer=signer)
Path("C_hibrid.pdf").write_bytes(o.getvalue())
r=PdfFileReader(io.BytesIO(o.getvalue())); st=validate_pdf_signature(r.embedded_signatures[0],vc)
print("C. hibrid: pagini",len(pikepdf.open("C_hibrid.pdf").pages),"| sigiliu dosar valid:",st.valid and st.intact)
for n,s in pikepdf.open("C_hibrid.pdf").attachments.items():
    d=s.get_file().read_bytes(); st=validate_pdf_signature(PdfFileReader(io.BytesIO(d)).embedded_signatures[0],vc)
    print("  atasat",n,"identic:",d==Path(n).read_bytes(),"semnatura valida:",st.valid and st.intact)
for x in info: print(" ",x)
