import sys
from xml.sax.saxutils import escape

import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

bahasa = Language(tscpp.language())
parser = Parser(bahasa)

nama_input = sys.argv[1] if len(sys.argv) > 1 else "input.cpp"
nama_output = sys.argv[2] if len(sys.argv) > 2 else "hasil.drawio"
kode = open(nama_input, "rb").read()
pohon = parser.parse(kode)

simpul = []         # (nomor, jenis, teks)
panah = []          # (dari, ke, label)
kolom = {}          # nomor -> nomor kolom
batas = []          # (a, b, selisih): tingkat b minimal tingkat a + selisih
tunda = []          # (a, selisih) untuk simpul berikutnya yang dibuat
lompat = {}         # nama label -> daftar asal goto yang menunggu
label_pertama = {}  # nama label -> nomor simpul pertama setelah label


def teks(node):
    return kode[node.start_byte:node.end_byte].decode("utf-8")


def rapikan(t):
    return " ".join(t.split())


def tambah(jenis_simpul, isi_teks, k):
    nomor = len(simpul) + 1
    simpul.append((nomor, jenis_simpul, isi_teks))
    kolom[nomor] = k
    for a, selisih in tunda:
        batas.append((a, nomor, selisih))
    tunda.clear()
    return nomor


def hubung(daftar_ujung, ke):
    for dari, label in daftar_ujung:
        panah.append((dari, ke, label))


def kondisi(node):
    t = teks(node.child_by_field_name("condition")).strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1]
    return t


def jenis_biasa(node):
    if node.type == "expression_statement":
        t = teks(node)
        if t.startswith("cin"):
            return "INPUT"
        if t.startswith("cout"):
            return "OUTPUT"
    return "PROSES"


def isi(node):
    if node.type == "compound_statement":
        return [c for c in node.named_children if c.type != "comment"]
    return [node]


def kondisi_for(node):
    c = node.child_by_field_name("condition")
    if c is None:
        return "true"
    return rapikan(teks(c))


def teks_bersih(node):
    return rapikan(teks(node)).rstrip(";").strip()


def berakhir(node):
    """True jika blok ini selalu ditutup dengan return atau goto."""
    daftar = isi(node)
    if not daftar:
        return False
    return daftar[-1].type in ("return_statement", "goto_statement")


def tutup_kumpulan(jenis_grup, kumpulan, masuk, k):
    """Gabungkan deklarasi beruntun (heksagon) atau input/output beruntun (jajar genjang)."""
    if not kumpulan:
        return masuk
    if jenis_grup == "decl":
        n = tambah("INISIALISASI", "<br>".join(teks_bersih(d) for d in kumpulan), k)
    else:
        jenis = "INPUT" if any(jenis_biasa(x) == "INPUT" for x in kumpulan) else "OUTPUT"
        n = tambah(jenis, "<br>".join(rapikan(teks(x)) for x in kumpulan), k)
    hubung(masuk, n)
    return [(n, None)]


def bangun(daftar, masuk, akhir, k):
    kumpulan = []
    jenis_grup = None
    for p in daftar:
        if p.type == "comment":
            continue
        if p.type == "declaration":
            grup = "decl"
        elif p.type == "expression_statement" and jenis_biasa(p) in ("INPUT", "OUTPUT"):
            grup = "io"
        else:
            grup = None
        if grup is not None and grup == jenis_grup:
            kumpulan.append(p)
            continue
        masuk = tutup_kumpulan(jenis_grup, kumpulan, masuk, k)
        kumpulan = []
        jenis_grup = None
        if grup is not None:
            kumpulan = [p]
            jenis_grup = grup
            continue
        if p.type == "for_statement":
            awal_for = p.child_by_field_name("initializer")
            if awal_for is not None:
                jenis_awal = "INISIALISASI" if awal_for.type == "declaration" else "PROSES"
                n_awal = tambah(jenis_awal, teks_bersih(awal_for), k)
                hubung(masuk, n_awal)
                masuk = [(n_awal, None)]
            n = tambah("KEPUTUSAN", kondisi_for(p), k)
            hubung(masuk, n)
            ujung = bangun(isi(p.child_by_field_name("body")), [(n, "Ya")], akhir, k)
            ubah = p.child_by_field_name("update")
            if ubah is not None and ujung:
                n_ubah = tambah("PROSES", teks_bersih(ubah), k)
                hubung(ujung, n_ubah)
                ujung = [(n_ubah, None)]
            hubung(ujung, n)
            masuk = [(n, "Tidak")]
        elif p.type == "while_statement":
            n = tambah("KEPUTUSAN", kondisi(p), k)
            hubung(masuk, n)
            ujung = bangun(isi(p.child_by_field_name("body")), [(n, "Ya")], akhir, k)
            hubung(ujung, n)
            masuk = [(n, "Tidak")]
        elif p.type == "if_statement":
            n = tambah("KEPUTUSAN", kondisi(p), k)
            hubung(masuk, n)
            cabang = p.child_by_field_name("consequence")
            alt = p.child_by_field_name("alternative")
            awal = len(simpul)
            if alt is None and berakhir(cabang):
                # cabang Ya berakhir (return/goto): taruh ke samping,
                # alur utama lanjut ke bawah lewat Tidak
                bangun(isi(cabang), [(n, "Ya")], akhir, k + 1)
                for s in simpul[awal:]:
                    tunda.append((s[0], 1))
                masuk = [(n, "Tidak")]
            else:
                ujung1 = bangun(isi(cabang), [(n, "Ya")], akhir, k)
                akhir_ya = len(simpul)
                kolom_terjauh = max([kolom[s[0]] for s in simpul[awal:]] + [k])
                if alt is not None:
                    ujung2 = bangun(isi(alt.named_children[0]), [(n, "Tidak")], akhir, kolom_terjauh + 1)
                else:
                    ujung2 = [(n, "Tidak")]
                if not ujung1:
                    for s in simpul[awal:akhir_ya]:
                        tunda.append((s[0], 1))
                masuk = ujung1 + ujung2
        elif p.type == "return_statement":
            n = tambah("PROSES", rapikan(teks(p)), k)
            hubung(masuk, n)
            akhir.append((n, None))
            masuk = []
        elif p.type == "goto_statement":
            nama = teks(p.named_children[0])
            if nama in label_pertama:
                hubung(masuk, label_pertama[nama])
            else:
                lompat.setdefault(nama, []).extend(masuk)
            masuk = []
        elif p.type == "labeled_statement":
            nama = teks(p.named_children[0])
            masuk = masuk + lompat.pop(nama, [])
            label_pertama[nama] = len(simpul) + 1
            masuk = bangun(p.named_children[1:], masuk, akhir, k)
        else:
            n = tambah(jenis_biasa(p), rapikan(teks(p)), k)
            hubung(masuk, n)
            masuk = [(n, None)]
    masuk = tutup_kumpulan(jenis_grup, kumpulan, masuk, k)
    return masuk


for fungsi in pohon.root_node.named_children:
    if fungsi.type == "function_definition":
        nama = rapikan(teks(fungsi.child_by_field_name("declarator")))
        badan = fungsi.child_by_field_name("body")
        mulai = tambah("TERMINATOR", "Mulai: " + nama, 0)
        akhir = []
        ujung = bangun(badan.named_children, [(mulai, None)], akhir, 0)
        selesai = tambah("TERMINATOR", "Selesai", 0)
        hubung(ujung + akhir, selesai)

# ===== TABEL GAYA (ubah gaya cukup di sini) =====
GAYA_UMUM = (
    "whiteSpace=wrap;html=1;fontSize=20;fontStyle=1;fontColor=#000000;"
    "strokeWidth=5;strokeColor=#000000;"
)
BENTUK = {
    "TERMINATOR": "rounded=1;arcSize=50;",
    "PROSES": "rounded=0;",
    "INPUT": "shape=parallelogram;perimeter=parallelogramPerimeter;spacingLeft=40;spacingRight=40;",
    "OUTPUT": "shape=parallelogram;perimeter=parallelogramPerimeter;spacingLeft=40;spacingRight=40;",
    "KEPUTUSAN": "rhombus;spacingLeft=50;spacingRight=50;",
    "INISIALISASI": "shape=hexagon;perimeter=hexagonPerimeter2;",
}
UKURAN = {
    "TERMINATOR": (280, 60),
    "PROSES": (300, 70),
    "INPUT": (360, 90),
    "OUTPUT": (360, 90),
    "KEPUTUSAN": (320, 120),
    "INISIALISASI": (380, 80),
}
# batas panjang teks per baris (lebih panjang dipotong dan diakhiri ...)
BATAS_TEKS = {
    "TERMINATOR": 28,
    "PROSES": 32,
    "INPUT": 32,
    "OUTPUT": 32,
    "KEPUTUSAN": 40,
    "INISIALISASI": 32,
}
# perkiraan jumlah karakter yang muat dalam satu baris bentuk
KARAKTER_PER_BARIS = {
    "TERMINATOR": 24,
    "PROSES": 28,
    "INPUT": 26,
    "OUTPUT": 26,
    "KEPUTUSAN": 16,
    "INISIALISASI": 28,
}
GAYA_PANAH = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;"
    "strokeWidth=5;fontSize=20;fontStyle=1;labelBackgroundColor=none;"
)
WARNA_PANAH = {
    "Ya": "strokeColor=#0000FF;fontColor=#0000FF;",
    "Tidak": "strokeColor=#FF0000;fontColor=#FF0000;",
    None: "strokeColor=#000000;fontColor=#000000;",
}
WARNA_BENTUK = {
    "TERMINATOR": "#FF66B3",
    "INISIALISASI": "#66FFB3",
    "PROSES": "#33FFFF",
    "INPUT": "#FFF4C3",
    "OUTPUT": "#FFF4C3",
    "KEPUTUSAN": "#6666FF",
}
JARAK = 40          # jarak vertikal antar baris
LEBAR_KOLOM = 520   # jarak antar kolom (cabang ke kanan)
MARGIN_KIRI = 260   # ruang di kiri untuk panah balik loop
JARAK_JALUR = 70    # jarak panah pengelilingi dari kotak
# =================================================

# --- Hitung tingkat (baris) tiap simpul ---
tingkat = {}
for nomor, j, t in simpul:
    syarat = []
    for d, k, l in panah:
        if k == nomor and d < nomor:
            syarat.append(tingkat[d] + 1)
            # keluar dari loop: harus di bawah seluruh isi loop
            for d2, k2, l2 in panah:
                if l == "Tidak" and k2 == d and d < d2 < nomor:
                    syarat.append(tingkat[d2] + 1)
    for a, b, selisih in batas:
        if b == nomor:
            syarat.append(tingkat[a] + selisih)
    tingkat[nomor] = max(syarat, default=0)


def potong(t, maks):
    if len(t) <= maks:
        return t
    t = t[:maks - 3]
    if " " in t:
        t = t[:t.rfind(" ")]
    return t.rstrip() + "..."


tampil = {n: "<br>".join(potong(b, BATAS_TEKS[j]) for b in t.split("<br>"))
          for n, j, t in simpul}


def ukuran_simpul(j, t):
    lebar, tinggi = UKURAN[j]
    per_baris = KARAKTER_PER_BARIS[j]
    baris = sum(max(1, -(-len(b) // per_baris)) for b in t.split("<br>"))
    return lebar, max(tinggi, 36 + 28 * baris)


tinggi_baris = {}
for nomor, j, t in simpul:
    lv = tingkat[nomor]
    tinggi_baris[lv] = max(tinggi_baris.get(lv, 0), ukuran_simpul(j, tampil[nomor])[1])

y_atas = {}
y_jalan = 20
for lv in sorted(tinggi_baris):
    y_atas[lv] = y_jalan
    y_jalan += tinggi_baris[lv] + JARAK

# --- Hitung posisi tiap simpul ---
LEBAR_MAKS = max(w for w, h in UKURAN.values())
G = {}  # nomor -> (x, y, lebar, tinggi)
for nomor, j, t in simpul:
    lebar, tinggi = ukuran_simpul(j, tampil[nomor])
    pusat_baris = y_atas[tingkat[nomor]] + tinggi_baris[tingkat[nomor]] / 2
    pusat_kolom = MARGIN_KIRI + LEBAR_MAKS / 2 + kolom[nomor] * LEBAR_KOLOM
    G[nomor] = (pusat_kolom - lebar / 2, pusat_baris - tinggi / 2, lebar, tinggi)


def pusat_x(n):
    return G[n][0] + G[n][2] / 2


def pusat_y(n):
    return G[n][1] + G[n][3] / 2


def titik(n, sisi):
    x, y, w, h = G[n]
    if sisi == "atas":
        return (x + w / 2, y)
    if sisi == "bawah":
        return (x + w / 2, y + h)
    if sisi == "kiri":
        return (x, y + h / 2)
    return (x + w, y + h / 2)


jalur_kiri = []   # (lv_awal, lv_akhir, x)
jalur_kanan = []  # (lv_awal, lv_akhir, x)


def nodes_antara(lv_awal, lv_akhir):
    return [n for n, j, t in simpul if lv_awal <= tingkat[n] <= lv_akhir]


def tentukan_jalur(dari, ke, label):
    """Kembalikan (sisi_keluar, sisi_masuk, titik_belok)."""
    if ke < dari:  # panah balik loop
        lo, hi = tingkat[ke], tingkat[dari]
        x = min(G[n][0] for n in nodes_antara(lo, hi))
        for a, b, xx in jalur_kiri:
            if not (b < lo or a > hi):
                x = min(x, xx)
        x -= JARAK_JALUR
        jalur_kiri.append((lo, hi, x))
        return "kiri", "kiri", [(x, pusat_y(dari)), (x, pusat_y(ke))]
    if kolom[ke] > kolom[dari]:  # cabang ke kanan
        return "kanan", "atas", [(pusat_x(ke), pusat_y(dari))]
    if kolom[ke] < kolom[dari]:  # cabang kembali ke kiri
        penghalang = [n for n in kolom
                      if kolom[n] == kolom[dari] and tingkat[dari] < tingkat[n] <= tingkat[ke]]
        if penghalang:  # ada kotak lain di bawahnya pada kolom yang sama: memutar lewat kanan
            lo, hi = tingkat[dari], tingkat[ke]
            x = max(G[n][0] + G[n][2] for n in kolom if kolom[n] == kolom[dari]
                    and lo <= tingkat[n] <= hi)
            for a, b, xx in jalur_kanan:
                if not (b < lo or a > hi):
                    x = max(x, xx)
            x += JARAK_JALUR
            jalur_kanan.append((lo, hi, x))
            return "kanan", "kanan", [(x, pusat_y(dari)), (x, pusat_y(ke))]
        return "bawah", "kanan", [(pusat_x(dari), pusat_y(ke))]
    # kolom sama: kalau ada kotak lain di antaranya, panah memutar lewat kanan
    penghalang = [n for n in kolom
                  if kolom[n] == kolom[dari] and tingkat[dari] < tingkat[n] < tingkat[ke]]
    if penghalang:
        lo, hi = tingkat[dari], tingkat[ke]
        x = max(G[n][0] + G[n][2] for n in nodes_antara(lo, hi))
        for a, b, xx in jalur_kanan:
            if not (b < lo or a > hi):
                x = max(x, xx)
        x += JARAK_JALUR
        jalur_kanan.append((lo, hi, x))
        y_belok = G[ke][1] - JARAK / 2
        return "kanan", "atas", [(x, pusat_y(dari)), (x, y_belok), (pusat_x(ke), y_belok)]
    return "bawah", "atas", []


SISI = {"atas": (0.5, 0), "bawah": (0.5, 1), "kiri": (0, 0.5), "kanan": (1, 0.5)}

sel = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
for nomor, j, t in simpul:
    x, y, lebar, tinggi = G[nomor]
    gaya = BENTUK[j] + GAYA_UMUM + f"fillColor={WARNA_BENTUK[j]};"
    sel.append(
        f'<mxCell id="n{nomor}" value="{escape(tampil[nomor], {chr(34): "&quot;"})}" '
        f'style="{gaya}" vertex="1" parent="1">'
        f'<mxGeometry x="{x:g}" y="{y:g}" width="{lebar}" height="{tinggi}" as="geometry"/>'
        f'</mxCell>'
    )

for i, (dari, ke, label) in enumerate(panah, start=1):
    keluar, masuk, belok = tentukan_jalur(dari, ke, label)
    ex, ey = SISI[keluar]
    nx, ny = SISI[masuk]
    gaya = (
        GAYA_PANAH
        + WARNA_PANAH[label]
        + f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
        + f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
    )
    jalan = [titik(dari, keluar)] + belok + [titik(ke, masuk)]
    panjang = sum(abs(jalan[m][0] - jalan[m + 1][0]) + abs(jalan[m][1] - jalan[m + 1][1])
                  for m in range(len(jalan) - 1))
    if keluar == "bawah":
        rel, off_x, off_y = 0, 30, 0
    else:
        rel = -1 + 2 * min(0.45, 45 / max(panjang, 1))
        off_x, off_y = 0, -14
    isi_belok = ""
    if belok:
        isi_belok = '<Array as="points">' + "".join(
            f'<mxPoint x="{bx:g}" y="{by:g}"/>' for bx, by in belok) + '</Array>'
    sel.append(
        f'<mxCell id="e{i}" value="{label or ""}" style="{gaya}" '
        f'edge="1" parent="1" source="n{dari}" target="n{ke}">'
        f'<mxGeometry x="{rel:g}" relative="1" as="geometry">'
        f'<mxPoint x="{off_x}" y="{off_y}" as="offset"/>{isi_belok}'
        f'</mxGeometry></mxCell>'
    )

xml = (
    '<mxfile><diagram name="main" id="main">'
    '<mxGraphModel><root>' + "".join(sel) + '</root></mxGraphModel>'
    '</diagram></mxfile>'
)
open(nama_output, "w", encoding="utf-8").write(xml)
print(f"File {nama_output} sudah dibuat")