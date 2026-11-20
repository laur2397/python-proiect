import io, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import pikepdf
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.pdf_utils import generic
from pyhanko.pdf_utils.content import RawContent
from pyhanko.sign import signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.keys import load_cert_from_pemder
from pyhanko_certvalidator import ValidationContext
vc=ValidationContext(trust_roots=[load_cert_from_pemder("ca.pem")])
signer=signers.SimpleSigner.load("key.pem","cert.pem",ca_chain_files=("ca.pem",))
def check(data,label):
    r=PdfFileReader(io.BytesIO(data))
    for s in r.embedded_signatures:
        st=validate_pdf_signature(s,vc)
        print(f"  {label} / {s.field_name}: intact={st.intact} valid={st.valid} acoperire={st.coverage.name} modificari={st.modification_level.name if st.modification_level else '-'} docmdp_ok={st.docmdp_ok}")

# A. pagini adaugate incremental la PDF-ul semnat (fara a rescrie ce exista)
w=IncrementalPdfFileWriter(io.BytesIO(Path("contract.pdf").read_bytes()))
src=PdfFileReader(io.BytesIO(Path("act_aditional.pdf").read_bytes()))
xobj=w.import_page_as_xobject(src,0)
res=generic.DictionaryObject({generic.NameObject('/XObject'):generic.DictionaryObject({generic.NameObject('/P0'):xobj})})
stream=generic.StreamObject(stream_data=b"q /P0 Do Q")
page=generic.DictionaryObject({generic.NameObject('/Type'):generic.NameObject('/Page'),generic.NameObject('/MediaBox'):generic.ArrayObject(map(generic.NumberObject,[0,0,612,792])),
  generic.NameObject('/Resources'):res,generic.NameObject('/Contents'):w.add_object(stream)})
w.insert_page(page)
out=io.BytesIO(); w.write(out); Path("A_incremental.pdf").write_bytes(out.getvalue())
print("A. Pagini adaugate incremental la contractul semnat:"); check(out.getvalue(),"A")

# B. portofoliu semnat la randul lui (sigiliul dosarului)
p=pikepdf.open("dosar_portofoliu.pdf"); p.save("tmp.pdf")
w=IncrementalPdfFileWriter(io.BytesIO(Path("tmp.pdf").read_bytes()))
o=signers.sign_pdf(w,signers.PdfSignatureMetadata(field_name="SigiliuDosar"),signer=signer)
Path("B_portofoliu_semnat.pdf").write_bytes(o.getvalue())
print("B. Portofoliu semnat de consultant:"); check(o.getvalue(),"dosar")
q=pikepdf.open("B_portofoliu_semnat.pdf")
for n,s in q.attachments.items(): check(s.get_file().read_bytes(),"  in dosar: "+n)
