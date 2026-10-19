import { useCallback, useRef, useState } from "react";
import { uploadInvoice } from "../api";

export default function UploadZone({ onUploaded }) {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const handleFiles = useCallback(
    async (files) => {
      if (!files || files.length === 0 || uploading) return;

      // Les doublons sont detectes cote serveur sur le contenu (hash), pas sur le nom :
      // deux factures differentes peuvent avoir le meme nom de fichier.
      const toUpload = Array.from(files);

      setUploading(true);
      setError(null);
      const errors = [];
      try {
        for (const file of toUpload) {
          try {
            const { data } = await uploadInvoice(file);
            onUploaded?.(data);
          } catch (err) {
            errors.push(`${file.name} : ${err.response?.data?.detail || "erreur lors de l'upload"}`);
          }
        }
        if (errors.length) setError(errors.join(" | "));
      } finally {
        setUploading(false);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [onUploaded, uploading]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors ${
        dragActive ? "border-primary-600 bg-primary-50" : "border-gray-300 bg-white"
      }`}
    >
      <p className="text-gray-600 mb-4">
        Glissez-deposez vos factures (PDF, PNG, JPG) ou
      </p>
      <label className="inline-block cursor-pointer bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg">
        {uploading ? "Envoi en cours..." : "Choisir un fichier"}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          multiple
          hidden
          disabled={uploading}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>
      {error && <p className="text-red-600 mt-3 text-sm">{error}</p>}
    </div>
  );
}
