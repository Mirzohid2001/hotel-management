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

export function ReferrersScreen({ onBack }: Props) {
  const { me, fetchReferrers, createReferrer, fetchCommission, payCommission } =
    useAuth();
  const canPay =
    me?.permissions?.pnl === true ||
    me?.permissions?.audit === true ||
    ["admin", "accountant"].includes(me?.role || "");

  const [tab, setTab] = useState<"list" | "commission">("list");
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [percent, setPercent] = useState("10");
  const [payId, setPayId] = useState<number | null>(null);
  const [payAmount, setPayAmount] = useState("");

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchReferrers());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchReferrers]);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await fetchCommission());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchCommission]);

  useEffect(() => {
    if (tab === "list") loadList();
    else loadReport();
  }, [tab, loadList, loadReport]);

  async function onCreate() {
    if (!name.trim()) return;
    try {
      await createReferrer({
        name: name.trim(),
        phone: phone.trim(),
        default_commission_percent: percent.trim() || "0",
      });
      setName("");
      setPhone("");
      setCreating(false);
      await loadList();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function onPay() {
    if (!payId || !payAmount.trim()) return;
    try {
      await payCommission(payId, payAmount.trim());
      setPayId(null);
      setPayAmount("");
      await loadReport();
      Alert.alert("Komissiya", "To‘landi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="CRM"
        title="Yo‘naltiruvchilar"
        onBack={onBack}
        right={
          tab === "list" ? (
            <Pressable style={ui.copperBtn} onPress={() => setCreating((v) => !v)}>
              <Text style={ui.copperBtnText}>{creating ? "Yopish" : "+ Yangi"}</Text>
            </Pressable>
          ) : null
        }
      />
      <View style={styles.tabs}>
        <Pressable
          style={[styles.tab, tab === "list" && styles.tabOn]}
          onPress={() => setTab("list")}
        >
          <Text style={[styles.tabText, tab === "list" && styles.tabTextOn]}>
            Ro‘yxat
          </Text>
        </Pressable>
        {canPay ? (
          <Pressable
            style={[styles.tab, tab === "commission" && styles.tabOn]}
            onPress={() => setTab("commission")}
          >
            <Text
              style={[styles.tabText, tab === "commission" && styles.tabTextOn]}
            >
              Komissiya
            </Text>
          </Pressable>
        ) : null}
      </View>

      {tab === "list" && creating ? (
        <View style={styles.pad}>
          <TextInput
            style={ui.input}
            placeholder="Ism *"
            value={name}
            onChangeText={setName}
            placeholderTextColor={colors.faint}
          />
          <TextInput
            style={ui.input}
            placeholder="Telefon"
            value={phone}
            onChangeText={setPhone}
            placeholderTextColor={colors.faint}
          />
          <TextInput
            style={ui.input}
            placeholder="Foiz %"
            value={percent}
            onChangeText={setPercent}
            keyboardType="decimal-pad"
            placeholderTextColor={colors.faint}
          />
          <Pressable style={ui.primaryBtn} onPress={onCreate}>
            <Text style={ui.primaryBtnText}>Saqlash</Text>
          </Pressable>
        </View>
      ) : null}

      {tab === "commission" && payId ? (
        <View style={styles.pad}>
          <TextInput
            style={ui.input}
            placeholder="To‘lov summasi"
            value={payAmount}
            onChangeText={setPayAmount}
            keyboardType="decimal-pad"
            placeholderTextColor={colors.faint}
          />
          <View style={styles.rowBtns}>
            <Pressable style={ui.copperBtn} onPress={() => setPayId(null)}>
              <Text style={ui.copperBtnText}>Bekor</Text>
            </Pressable>
            <Pressable style={[ui.primaryBtn, { flex: 1 }]} onPress={onPay}>
              <Text style={ui.primaryBtnText}>To‘lash</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {loading ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 24 }} />
      ) : tab === "list" ? (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={loadList} tintColor={colors.accent} />
          }
          ListEmptyComponent={<Text style={ui.empty}>Yo‘naltiruvchi yo‘q</Text>}
          renderItem={({ item }) => (
            <View style={ui.rowItem}>
              <Text style={ui.rowTitle}>{String(item.name)}</Text>
              <Text style={ui.rowMeta}>
                {String(item.phone || "—")} · {String(item.default_commission_percent)}%
              </Text>
            </View>
          )}
        />
      ) : (
        <FlatList
          data={(report?.items as Record<string, unknown>[]) || []}
          keyExtractor={(i) => String(i.referrer_id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={loadReport} tintColor={colors.accent} />
          }
          ListHeaderComponent={
            report ? (
              <Text style={[ui.rowMeta, { marginBottom: 12 }]}>
                Jami: {String(report.grand_commission)} · Qoldiq:{" "}
                {String(report.grand_remaining)}
              </Text>
            ) : null
          }
          ListEmptyComponent={<Text style={ui.empty}>Komissiya yo‘q</Text>}
          renderItem={({ item }) => (
            <Pressable
              style={ui.rowItem}
              onPress={() => {
                setPayId(Number(item.referrer_id));
                setPayAmount(String(item.remaining || ""));
              }}
            >
              <Text style={ui.rowTitle}>{String(item.name)}</Text>
              <Text style={ui.rowMeta}>
                {String(item.count)} bron · {String(item.commission_total)} · qoldiq{" "}
                {String(item.remaining)}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  tabs: {
    flexDirection: "row",
    paddingHorizontal: space.lg,
    gap: 8,
    marginTop: space.sm,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: colors.paperDeep,
    alignItems: "center",
  },
  tabOn: { backgroundColor: colors.accent },
  tabText: { fontWeight: "700", color: colors.inkSoft },
  tabTextOn: { color: colors.white },
  pad: { paddingHorizontal: space.lg, paddingTop: space.md, gap: space.sm },
  rowBtns: { flexDirection: "row", gap: 10, alignItems: "center" },
});
