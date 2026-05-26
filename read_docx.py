import zipfile
import xml.etree.ElementTree as ET
import os

def read_docx(docx_path):
    if not os.path.exists(docx_path):
        return f"File {docx_path} does not exist"
    try:
        with zipfile.ZipFile(docx_path) as z:
            xml_content = z.read("word/document.xml")
            root = ET.fromstring(xml_content)
            text_parts = []
            for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                p_text = []
                for run in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                    if run.text:
                        p_text.append(run.text)
                text_parts.append("".join(p_text))
            return "\n".join(text_parts)
    except Exception as e:
        return f"Error reading {docx_path}: {e}"

full_text = read_docx(r"C:\Users\The One\Desktop\Introduce Yourself.docx")
with open(r"c:\Users\The One\Desktop\BEL\intro_yourself.txt", "w", encoding="utf-8") as f:
    f.write(full_text)
print("Done writing to intro_yourself.txt")
