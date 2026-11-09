import sys, zipfile
from xml.etree import ElementTree as ET
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

def text_of(el):
    out = []
    for n in el.iter():
        if n.tag == W + "t": out.append(n.text or "")
        elif n.tag == W + "tab": out.append("\t")
        elif n.tag in (W + "br", W + "cr"): out.append("\n")
    return "".join(out)

def dump(path):
    z = zipfile.ZipFile(path)
    rels = {r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("word/_rels/document.xml.rels")).iter(REL + "Relationship")}
    doc = ET.fromstring(z.read("word/document.xml"))
    print("=" * 78); print("FILE:", path); print("=" * 78)
    body = doc.find(W + "body")
    for child in body:
        if child.tag == W + "p":
            t = text_of(child).strip()
            style = child.find(f"{W}pPr/{W}pStyle")
            num = child.find(f"{W}pPr/{W}numPr")
            tag = ("[" + style.get(W + "val") + "] ") if style is not None else ""
            if num is not None: tag += "- "
            pics = [rels.get(b.get(R + "embed")) for b in child.iter(A + "blip")]
            if t: print(tag + t)
            for p in pics: print("   IMG>", p)
        elif child.tag == W + "tbl":
            print("\n[TABLE]")
            for row in child.iter(W + "tr"):
                cells = [text_of(c).strip().replace("\n", " / ") for c in row.findall(W + "tc")]
                print("  | " + " | ".join(cells))
            print("[/TABLE]\n")
    if "word/comments.xml" in z.namelist():
        print("\n----- COMMENTS -----")
        for c in ET.fromstring(z.read("word/comments.xml")).iter(W + "comment"):
            print(f"[{c.get(W+'id')}] {c.get(W+'author','?')}: {text_of(c).strip()}")

for p in sys.argv[1:]:
    dump(p)
