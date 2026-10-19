"""Genere des factures PDF synthetiques pour tester InvoiceIQ."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUTPUT_DIR = Path(__file__).parent

INVOICES = [
    {
        "filename": "facture_001_techsupply.pdf",
        "invoice_number": "INV-2026-001",
        "invoice_date": "2026-01-15",
        "supplier": "TechSupply SARL",
        "supplier_addr": "12 rue de l'Innovation, 75011 Paris",
        "client": "Acme Corp",
        "client_addr": "45 avenue des Entreprises, 69002 Lyon",
        "items": [("Ordinateur portable Dell XPS 15", 2, 1200.00), ("Souris sans fil Logitech", 5, 25.00)],
        "tva_rate": 0.20,
    },
    {
        "filename": "facture_002_greenenergy.pdf",
        "invoice_number": "F-2026-0456",
        "invoice_date": "2026-02-03",
        "supplier": "GreenEnergy Solutions",
        "supplier_addr": "8 boulevard Solaire, 33000 Bordeaux",
        "client": "Restaurant Le Gourmet",
        "client_addr": "3 place du Marche, 33800 Bordeaux",
        "items": [("Installation panneaux solaires", 1, 8500.00), ("Maintenance annuelle", 1, 450.00)],
        "tva_rate": 0.20,
    },
    {
        "filename": "facture_003_office.pdf",
        "invoice_number": "OFF-2026-789",
        "invoice_date": "2026-03-10",
        "supplier": "OfficePro Fournitures",
        "supplier_addr": "22 rue du Commerce, 59000 Lille",
        "client": "Cabinet Juridique Martin",
        "client_addr": "15 rue de la Loi, 59800 Lille",
        "items": [("Ramettes papier A4 (x10)", 3, 35.00), ("Cartouches d'encre HP", 8, 22.50), ("Chaises de bureau ergonomiques", 4, 180.00)],
        "tva_rate": 0.20,
    },
]


def build_invoice_pdf(data: dict) -> None:
    path = OUTPUT_DIR / data["filename"]
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    y = height - 30 * mm
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, y, data["supplier"])
    c.setFont("Helvetica", 10)
    y -= 6 * mm
    c.drawString(20 * mm, y, data["supplier_addr"])

    y -= 15 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, f"FACTURE {data['invoice_number']}")
    c.setFont("Helvetica", 10)
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Date: {data['invoice_date']}")

    y -= 12 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Client:")
    c.setFont("Helvetica", 10)
    y -= 5 * mm
    c.drawString(20 * mm, y, data["client"])
    y -= 5 * mm
    c.drawString(20 * mm, y, data["client_addr"])

    y -= 15 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Description")
    c.drawString(110 * mm, y, "Qte")
    c.drawString(130 * mm, y, "Prix unitaire")
    c.drawString(165 * mm, y, "Total")
    y -= 3 * mm
    c.line(20 * mm, y, 190 * mm, y)

    total_ht = 0.0
    c.setFont("Helvetica", 10)
    for label, qty, unit_price in data["items"]:
        y -= 7 * mm
        line_total = qty * unit_price
        total_ht += line_total
        c.drawString(20 * mm, y, label)
        c.drawString(112 * mm, y, str(qty))
        c.drawString(130 * mm, y, f"{unit_price:.2f} EUR")
        c.drawString(165 * mm, y, f"{line_total:.2f} EUR")

    tva = round(total_ht * data["tva_rate"], 2)
    ttc = round(total_ht + tva, 2)

    y -= 12 * mm
    c.line(120 * mm, y, 190 * mm, y)
    y -= 7 * mm
    c.drawString(130 * mm, y, "Montant HT:")
    c.drawString(165 * mm, y, f"{total_ht:.2f} EUR")
    y -= 7 * mm
    c.drawString(130 * mm, y, f"TVA ({int(data['tva_rate'] * 100)}%):")
    c.drawString(165 * mm, y, f"{tva:.2f} EUR")
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(130 * mm, y, "Montant TTC:")
    c.drawString(165 * mm, y, f"{ttc:.2f} EUR")

    c.showPage()
    c.save()
    print(f"Cree: {path} (HT={total_ht:.2f}, TVA={tva:.2f}, TTC={ttc:.2f})")


if __name__ == "__main__":
    for invoice in INVOICES:
        build_invoice_pdf(invoice)
