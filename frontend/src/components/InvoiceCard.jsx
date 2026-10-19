import { useState } from "react";
import { deleteInvoice, exportInvoice, extractInvoice } from "../api";

const STATUS_LABELS = {
  uploaded: { label: "Upload...", color: "bg-gray-100 text-gray-700" },
  ocr_done: { label: "OCR termine", color: "bg-yellow-100 text-yellow-700" },
  ocr_failed: { label: "OCR echoue", color: "bg-red-100 text-red-700" },
  indexed: { label: "En attente d'extraction", color: "bg-blue-100 text-blue-700" },
  extraction_failed: { label: "Extraction echouee", color: "bg-red-100 text-red-700" },
  extracted: { label: "Extraite", color: "bg-green-100 text-green-700" },
};

const formatAmount = (amount, currency) => {
  if (amount == null) return "—";
  const value = Number(amount);
  if (Number.isNaN(value)) return "—";
  return `${value.toFixed(2)} ${currency || "(devise ?)"}`;
};

export default function InvoiceCard({ invoice, selected, onToggleSelect, onChanged }) {
  const [busy, setBusy] = useState(false);
  const status = STATUS_LABELS[invoice.status] || { label: invoice.status, color: "bg-gray-100 text-gray-700" };
  const needsExtraction = invoice.status !== "extracted" && invoice.status !== "ocr_failed";
  const notes = invoice.validation_notes || [];

  const stop = (e) => e.stopPropagation();

  const handleExport = async (e) => {
    stop(e);
    const { data } = await exportInvoice(invoice.id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `facture_${invoice.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExtract = async (e) => {
    stop(e);
    setBusy(true);
    try {
      await extractInvoice(invoice.id);
      onChanged?.();
    } catch (err) {
      alert(`Echec de l'extraction : ${err.response?.data?.detail || "verifie ta cle GROQ_API_KEY dans .env"}`);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (e) => {
    stop(e);
    if (!window.confirm(`Supprimer definitivement "${invoice.filename}" ?`)) return;
    setBusy(true);
    try {
      await deleteInvoice(invoice.id);
      onChanged?.();
    } catch {
      alert("Echec de la suppression.");
      setBusy(false);
    }
  };

  return (
    <div
      onClick={() => onToggleSelect?.(invoice.id)}
      className={`bg-white rounded-lg shadow-sm border p-4 cursor-pointer transition ${
        selected ? "border-primary-600 ring-2 ring-primary-100" : "border-gray-200 hover:border-gray-300"
      } ${busy ? "opacity-50 pointer-events-none" : ""}`}
    >
      <div className="flex justify-between items-start gap-2">
        <div className="min-w-0">
          <p className="font-medium truncate">{invoice.filename}</p>
          <p className="text-sm text-gray-500 truncate">
            {invoice.invoice_number || "N° inconnu"} — {invoice.supplier_name || "Fournisseur inconnu"}
          </p>
        </div>
        <div className="shrink-0 flex flex-col items-end gap-1">
          <span className={`text-xs px-2 py-1 rounded-full ${status.color}`}>{status.label}</span>
          {invoice.needs_review && (
            <span
              title={notes.join("\n")}
              className="text-xs px-2 py-1 rounded-full bg-orange-100 text-orange-700"
            >
              A verifier
            </span>
          )}
        </div>
      </div>

      {invoice.needs_review && notes.length > 0 && (
        <ul className="mt-2 text-xs text-orange-700 list-disc list-inside">
          {notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}

      <div className="flex justify-between items-center mt-3">
        <p className="text-lg font-semibold">
          {formatAmount(invoice.amount_ttc, invoice.currency)}
        </p>
        <div className="flex items-center gap-3 text-sm">
          {needsExtraction && (
            <button onClick={handleExtract} className="text-primary-600 hover:underline">
              {invoice.status === "indexed" ? "Extraire" : "Re-extraire"}
            </button>
          )}
          <button onClick={handleExport} className="text-primary-600 hover:underline">
            Exporter
          </button>
          <button onClick={handleDelete} className="text-red-600 hover:underline">
            Supprimer
          </button>
        </div>
      </div>
    </div>
  );
}
