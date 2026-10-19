import { useEffect, useState } from "react";
import UploadZone from "../components/UploadZone";
import InvoiceCard from "../components/InvoiceCard";
import ChatInterface from "../components/ChatInterface";
import { listInvoices } from "../api";

export default function Home() {
  const [invoices, setInvoices] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);

  const refresh = async () => {
    try {
      const { data } = await listInvoices();
      setInvoices(Array.isArray(data) ? data : []);
    } catch {
      setInvoices([]);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const toggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <div className="max-w-6xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="space-y-6">
        <UploadZone onUploaded={refresh} />
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-lg">Factures ({invoices.length})</h2>
            {selectedIds.length > 0 && (
              <button
                onClick={() => setSelectedIds([])}
                className="text-sm text-gray-500 hover:underline"
              >
                Deselectionner ({selectedIds.length})
              </button>
            )}
          </div>
          {invoices.map((inv) => (
            <InvoiceCard
              key={inv.id}
              invoice={inv}
              selected={selectedIds.includes(inv.id)}
              onToggleSelect={toggleSelect}
              onChanged={refresh}
            />
          ))}
          {invoices.length === 0 && (
            <p className="text-gray-400 text-sm">Aucune facture pour le moment. Uploade un PDF ou une image pour commencer.</p>
          )}
        </div>
      </div>
      <ChatInterface selectedInvoiceIds={selectedIds} />
    </div>
  );
}
