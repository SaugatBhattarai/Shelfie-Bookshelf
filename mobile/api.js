export const BASE = "http://192.168.2.202:8000";   // your ipconfig IPv4

export async function uploadShelf(uri) {
  const form = new FormData();
  form.append("image", { uri, name: "shelf.jpg", type: "image/jpeg" });

  const res = await fetch(`${BASE}/api/scans/`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function confirmBooks(scanId, books) {
  const res = await fetch(`${BASE}/api/library/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scan_id: scanId, books }),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}