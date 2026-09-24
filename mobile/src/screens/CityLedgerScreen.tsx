import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

export function CityLedgerScreen({ onBack }: Props) {
  const { fetchCityLedger, payCityLedger } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [payingId, setPayingId] = useState<number | null>(null);
  const [amount, setAmount] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchCityLedger("open"));
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchCityLedger]);

  useEffect(() => {
    load();
  }, [load]);

  async function submitPay() {
    if (payingId == null || !amount.trim()) return;
    try {
      await payCityLedger(payingId, amount.trim());
      setPayingId(null);
      setAmount("");
      await load();
      Alert.alert("City ledger", "To‘lov yozildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader eyebrow="Moliya" title="City ledger" onBack={onBack} />
      {payingId != null ? (
        <View style={styles.payBox}>
          <Text style={ui.rowTitle}>To‘lov summasi</Text>
          <TextInput
            style={ui.input}
            value={amount}
            onChangeText={setAmount}
            keyboardType="decimal-pad"
            placeholderTextColor={colors.faint}
          />
          <Pressable style={ui.primaryBtn} onPress={submitPay}>
            <Text style={ui.primaryBtnText}>To‘lash</Text>
          </Pressable>
          <Pressable
            style={[ui.primaryBtn, { backgroundColor: colors.night, marginTop: 8 }]}
            onPress={() => setPayingId(null)}
          >
            <Text style={ui.primaryBtnText}>Bekor</Text>
          </Pressable>
        </View>
      ) : null}
      {loading && !items.length ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />
          }
          ListEmptyComponent={<Text style={ui.empty}>Ochiq hisob-faktura yo‘q</Text>}
          renderItem={({ item }) => (
            <Pressable
              style={ui.rowItem}
              onPress={() => {
                setPayingId(Number(item.id));
                setAmount(String(item.balance || ""));
              }}
            >
              <Text style={ui.rowTitle}>
                {String(item.code)} · {String(item.company)}
              </Text>
              <Text style={ui.rowMeta}>
                {String(item.status)} · jami {String(item.total)} · qoldiq{" "}
                {String(item.balance)} · to‘lash ›
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  payBox: {
    margin: space.lg,
    padding: space.lg,
    backgroundColor: colors.surface,
    borderRadius: 14,
  },
});
