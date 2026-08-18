import { useState } from "react";
import { View, Text, Button, Image, ScrollView, ActivityIndicator } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { uploadShelf } from "./api";

const COLOR = { high: "#1d7a4f", review: "#b8860b", unmatched: "#b00020" };

export default function App() {
  const [photo, setPhoto] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function pickAndUpload() {
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.7,
    });
    if (picked.canceled) return;

    setPhoto(picked.assets[0].uri);
    setResult(null);
    setError(null);
    setBusy(true);
    try {
      setResult(await uploadShelf(picked.assets[0].uri));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 70, gap: 14 }}>
      <Button title="Pick shelf photo" onPress={pickAndUpload} />

      {photo && <Image source={{ uri: photo }} style={{ height: 200, borderRadius: 6 }} />}
      {busy && <ActivityIndicator />}
      {error && <Text style={{ color: COLOR.unmatched }}>{error}</Text>}

      {result?.detections.length === 0 && !busy && (
        <Text>No books found. Try a straighter, closer photo.</Text>
      )}

      {result?.detections.map((d, i) => (
        <View key={i}>
          <Text style={{ fontSize: 16 }}>
            {d.match.title ?? d.raw_read.title ?? "Unreadable spine"}
          </Text>
          <Text style={{ fontSize: 13, color: COLOR[d.match.status] }}>
            {d.match.author ?? "—"} · {d.match.status} · {d.match.score.toFixed(2)}
          </Text>
        </View>
      ))}

      {result && (
        <Text style={{ fontSize: 12, color: "#888" }}>
          {JSON.stringify(result.timings_ms)}
        </Text>
      )}
    </ScrollView>
  );
}