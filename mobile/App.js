import { useState } from "react";
import {
  View, Text, Button, Image, ScrollView, ActivityIndicator, Pressable,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { uploadShelf, confirmBooks, fetchLibrary } from "./api";

const COLOR = { high: "#1d7a4f", review: "#b8860b", unmatched: "#b00020" };

export default function App() {
  const [photo, setPhoto] = useState(null);
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState({});   // index -> bool
  const [library, setLibrary] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleAsset(asset) {
    setPhoto(asset.uri);
    setResult(null);
    setSelected({});
    setError(null);
    setBusy(true);
    try {
      const data = await uploadShelf(asset);
      setResult(data);
      const preselected = {};
      data.detections.forEach((d, i) => {
        if (d.match.status === "high") preselected[i] = true;
      });
      setSelected(preselected);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function takePhoto() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      setError("Camera permission denied. Pick from library instead.");
      return;
    }
    const shot = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!shot.canceled) handleAsset(shot.assets[0]);
  }

  async function pickPhoto() {
    const picked = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
    if (!picked.canceled) handleAsset(picked.assets[0]);
  }

  async function save() {
    const books = result.detections
      .filter((_, i) => selected[i])
      .map((d) => ({
        catalog_id: d.match.catalog_id,
        title: d.match.title ?? d.raw_read.title,
        author: d.match.author ?? d.raw_read.author,
      }));

    setBusy(true);
    setError(null);
    try {
      await confirmBooks(result.scan_id, books);
      setLibrary(await fetchLibrary());
      setResult(null);
      setPhoto(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const chosen = Object.values(selected).filter(Boolean).length;

  return (
    <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 70, gap: 14 }}>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <Button title="Take photo" onPress={takePhoto} />
        <Button title="Pick photo" onPress={pickPhoto} />
      </View>

      {photo && <Image source={{ uri: photo }} style={{ height: 180, borderRadius: 6 }} />}
      {busy && <ActivityIndicator />}
      {error && <Text style={{ color: COLOR.unmatched }}>{error}</Text>}

      {result?.detections.length === 0 && !busy && (
        <Text>No books found. Try a straighter, closer photo.</Text>
      )}

      {result?.detections.map((d, i) => (
        <Pressable
          key={i}
          onPress={() => setSelected((s) => ({ ...s, [i]: !s[i] }))}
          style={{
            padding: 12,
            borderRadius: 6,
            borderWidth: 1,
            borderColor: selected[i] ? COLOR.high : "#ddd",
            backgroundColor: selected[i] ? "#f2f9f5" : "#fff",
          }}
        >
          <Text style={{ fontSize: 16 }}>
            {d.match.title ?? d.raw_read.title ?? "Unreadable spine"}
          </Text>
          <Text style={{ fontSize: 13, color: COLOR[d.match.status] }}>
            {d.match.author ?? "unknown author"} · {d.match.status} ·{" "}
            {d.match.score.toFixed(2)}
          </Text>
          {d.alternates?.length > 0 && (
            <Text style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              also matched: {d.alternates.map((a) => a.title).join(", ")}
            </Text>
          )}
        </Pressable>
      ))}

      {result?.detections.length > 0 && (
        <Button title={`Add ${chosen} to library`} onPress={save} disabled={chosen === 0} />
      )}

      {result && (
        <Text style={{ fontSize: 12, color: "#888" }}>
          {JSON.stringify(result.timings_ms)}
        </Text>
      )}

      {library.length > 0 && (
        <View style={{ marginTop: 20, gap: 6 }}>
          <Text style={{ fontSize: 18 }}>Library ({library.length})</Text>
          {library.map((b) => (
            <Text key={b.id} style={{ fontSize: 14 }}>
              {b.title} — {b.author || "unknown"}
            </Text>
          ))}
        </View>
      )}
    </ScrollView>
  );
}