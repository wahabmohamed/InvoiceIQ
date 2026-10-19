import { useState } from "react";
import { chat as chatApi } from "../api";

// Rendu minimal du gras Markdown (**texte**) renvoye par le LLM
function renderText(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      part
    )
  );
}

function MessageBubble({ message }) {
  const [showSources, setShowSources] = useState(false);
  const sources = message.sources || [];
  const uniqueSources = sources.filter(
    (s, i) => sources.findIndex((o) => o.content === s.content) === i
  );

  return (
    <div className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
          message.role === "user"
            ? "bg-primary-600 text-white"
            : message.error
            ? "bg-red-50 text-red-700"
            : "bg-gray-100 text-gray-800"
        }`}
      >
        <p className="whitespace-pre-wrap">{renderText(message.content)}</p>
        {message.standaloneQuestion && (
          <p className="mt-1 text-xs text-gray-400">Recherche effectuee : « {message.standaloneQuestion} »</p>
        )}
        {uniqueSources.length > 0 && (
          <button
            onClick={() => setShowSources((v) => !v)}
            className="mt-2 text-xs text-gray-500 underline block"
          >
            {showSources ? "Masquer les extraits" : `Extraits consultes (${uniqueSources.length})`}
          </button>
        )}
        {showSources && (
          <div className="mt-2 border-t pt-2 space-y-1">
            <p className="text-xs text-gray-400">
              Passages fournis au modele (les montants et totaux proviennent des donnees extraites).
            </p>
            {uniqueSources.map((s, j) => (
              <p key={j} className="text-xs text-gray-500 italic">
                [Facture {s.invoice_id} · {s.filename}
                {s.score != null ? ` · similarite ${(s.score * 100).toFixed(0)}%` : ""}] : "
                {/* 1re ligne = en-tete technique du chunk : on affiche le contenu */}
                {(s.content.split("\n").slice(1).join(" ") || s.content).slice(0, 160)}..."
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatInterface({ selectedInvoiceIds }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const question = input.trim();
    const nextMessages = [...messages, { role: "user", content: question }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      // Historique = messages PRECEDENTS uniquement (la question courante est envoyee
      // a part) ; les messages d'erreur ne sont pas renvoyes au LLM.
      const history = messages
        .filter((m) => !m.error)
        .slice(-6)
        .map(({ role, content }) => ({ role, content }));
      const { data } = await chatApi(question, selectedInvoiceIds, history);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          standaloneQuestion: data.standalone_question,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Erreur: ${err.response?.data?.detail || "impossible d'obtenir une reponse."}`,
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border flex flex-col h-[600px]">
      <div className="p-4 border-b">
        <h3 className="font-semibold">Chat Q&A</h3>
        <p className="text-xs text-gray-500">
          {selectedInvoiceIds?.length
            ? `${selectedInvoiceIds.length} facture(s) selectionnee(s)`
            : "Toutes les factures"}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {loading && <p className="text-sm text-gray-400">InvoiceIQ reflechit...</p>}
      </div>
      <div className="p-3 border-t flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Posez une question sur vos factures..."
          className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <button
          onClick={handleSend}
          disabled={loading}
          className="bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
        >
          Envoyer
        </button>
      </div>
    </div>

  );
}
