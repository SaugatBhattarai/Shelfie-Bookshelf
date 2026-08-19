export const BASE = "http://172.20.10.3:8000"; 

export async function uploadShelf(asset) {
  const form = new FormData();
  form.append("image", {
    uri: asset.uri,
    name: asset.fileName ?? "shelf.jpg",
    type: asset.mimeType ?? "image/jpeg",
  });

  const res = await fetch(`${BASE}/api/scans/`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed (${res.status})`);
  return res.json();
}

export async function confirmBooks(scanId, books) {
  const res = await fetch(`${BASE}/api/library/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scan_id: scanId, books }),
  });
  if (!res.ok) throw new Error(`Save failed (${res.status})`);
  return res.json();
}

export async function fetchLibrary() {
  const res = await fetch(`${BASE}/api/library/`);
  if (!res.ok) throw new Error(`Load failed (${res.status})`);
  return res.json();
}