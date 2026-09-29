import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  SegmentedTabs,
  StatsStrip,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";
import { sharePdfBase64 } from "../utils/sharePdf";

type Props = { onBack: () => void };

export function ReferrersScreen({ onBack }: Props) {
  const {
    me,
    fetchReferrers,
    createReferrer,
    updateReferrer,
    fetchCommission,
    payCommission,
    printCommission,
  } = useAuth();
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
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editPercent, setEditPercent] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

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
      setReport(await fetchCommission(year, month));
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchCommission, year, month]);

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
      await payCommission(payId, payAmount.trim(), { year, month });
      setPayId(null);
      setPayAmount("");
      await loadReport();
      Alert.alert("Komissiya", "To‘landi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  function openEdit(item: Record<string, unknown>) {
    setCreating(false);
    setEditing(item);
    setEditName(String(item.name || ""));
    setEditPhone(String(item.phone || ""));
    setEditPercent(String(item.default_commission_percent ?? ""));
    setEditActive(item.is_active !== false);
  }

  async function onSaveEdit() {
    if (!editing || !editName.trim()) return;
    setBusy(true);
    try {
      await updateReferrer(Number(editing.id), {
        name: editName.trim(),
        phone: editPhone.trim(),
        default_commission_percent: editPercent.trim() || "0",
        is_active: editActive,
      });
      setEditing(null);
      await loadList();
      Alert.alert("OK", "Saqlandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  const tabs: { id: "list" | "commission"; label: string }[] = canPay
    ? [
        { id: "list", label: "Ro‘yxat" },
        { id: "commission", label: "Komissiya" },
      ]
    : [{ id: "list", label: "Ro‘yxat" }];

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="CRM"
        title="Yo‘naltiruvchilar"
        subtitle={
          tab === "list"
            ? items.length
              ? `${items.length} ta yo‘naltiruvchi`
              : "Hamkorlar ro‘yxati"
            : "Komissiya hisoboti"
        }
        onBack={onBack}
        right={
          tab === "list" ? (
            <Pressable
              style={({ pressed }) => [
                ui.copperBtn,
                pressed && { opacity: 0.85 },
              ]}
              onPress={() => {
                setEditing(null);
                setCreating((v) => !v);
              }}
            >
              <Text style={ui.copperBtnText}>
                {creating ? "Yopish" : "+ Yangi"}
              </Text>
            </Pressable>
          ) : null
        }
      />

      {tabs.length > 1 ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <SegmentedTabs tabs={tabs} value={tab} onChange={setTab} />
        </View>
      ) : null}

      {tab === "list" && creating ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>Ism *</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="To‘liq ism"
              value={name}
              onChangeText={setName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Telefon</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="+998…"
              value={phone}
              onChangeText={setPhone}
              placeholderTextColor={colors.faint}
              keyboardType="phone-pad"
            />
            <FieldLabel>Foiz %</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="10"
              value={percent}
              onChangeText={setPercent}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <PrimaryButton label="Saqlash" onPress={onCreate} />
          </FormCard>
        </View>
      ) : null}

      {tab === "list" && editing ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>Ism *</FieldLabel>
            <TextInput
              style={ui.input}
              value={editName}
              onChangeText={setEditName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Telefon</FieldLabel>
            <TextInput
              style={ui.input}
              value={editPhone}
              onChangeText={setEditPhone}
              placeholderTextColor={colors.faint}
              keyboardType="phone-pad"
            />
            <FieldLabel>Foiz %</FieldLabel>
            <TextInput
              style={ui.input}
              value={editPercent}
              onChangeText={setEditPercent}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Holat</FieldLabel>
            <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
              <Pressable
                style={[ui.chip, editActive && ui.chipOn]}
                onPress={() => setEditActive(true)}
              >
                <Text style={[ui.chipText, editActive && ui.chipTextOn]}>
                  Faol
                </Text>
              </Pressable>
              <Pressable
                style={[ui.chip, !editActive && ui.chipOn]}
                onPress={() => setEditActive(false)}
              >
                <Text style={[ui.chipText, !editActive && ui.chipTextOn]}>
                  O‘chiq
                </Text>
              </Pressable>
            </View>
            <PrimaryButton
              label="Saqlash"
              onPress={onSaveEdit}
              loading={busy}
            />
            <PrimaryButton
              label="Bekor"
              onPress={() => setEditing(null)}
              tone="ghost"
            />
          </FormCard>
        </View>
      ) : null}

      {tab === "commission" && payId ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>To‘lov summasi</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="0.00"
              value={payAmount}
              onChangeText={setPayAmount}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <PrimaryButton label="To‘lash" onPress={onPay} />
            <PrimaryButton
              label="PDF chek"
              tone="ghost"
              onPress={async () => {
                if (!payId) return;
                setBusy(true);
                try {
                  const file = await printCommission(payId, year, month);
                  await sharePdfBase64(
                    file.pdf_base64,
                    file.filename || `commission-${payId}.pdf`
                  );
                } catch (e) {
                  Alert.alert(
                    "PDF",
                    e instanceof ApiError ? e.message : "Chop etish xatosi"
                  );
                } finally {
                  setBusy(false);
                }
              }}
              loading={busy}
            />
            <PrimaryButton
              label="Bekor"
              onPress={() => setPayId(null)}
              tone="ghost"
            />
          </FormCard>
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
            <RefreshControl
              refreshing={loading}
              onRefresh={loadList}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState
              title="Yo‘naltiruvchi yo‘q"
              hint="Yangi hamkor qo‘shing"
            />
          }
          renderItem={({ item }) => (
            <ListCard
              title={String(item.name)}
              meta={`${String(item.phone || "—")} · ${String(item.default_commission_percent)}%`}
              badge={`${String(item.default_commission_percent)}%`}
              badgeTone="accent"
              leading={<AvatarMark label={String(item.name)} />}
              onPress={() => openEdit(item)}
            />
          )}
        />
      ) : (
        <FlatList
          data={(report?.items as Record<string, unknown>[]) || []}
          keyExtractor={(i) => String(i.referrer_id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={loadReport}
              tintColor={colors.accent}
            />
          }
          ListHeaderComponent={
            report ? (
              <View style={{ marginBottom: space.sm, marginHorizontal: -space.lg }}>
                <View
                  style={{
                    flexDirection: "row",
                    flexWrap: "wrap",
                    gap: 8,
                    paddingHorizontal: space.lg,
                    marginBottom: space.sm,
                  }}
                >
                  {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
                    <Pressable
                      key={y}
                      style={[ui.chip, y === year && ui.chipOn]}
                      onPress={() => setYear(y)}
                    >
                      <Text style={[ui.chipText, y === year && ui.chipTextOn]}>
                        {y}
                      </Text>
                    </Pressable>
                  ))}
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <Pressable
                      key={m}
                      style={[ui.chip, m === month && ui.chipOn]}
                      onPress={() => setMonth(m)}
                    >
                      <Text style={[ui.chipText, m === month && ui.chipTextOn]}>
                        {m}
                      </Text>
                    </Pressable>
                  ))}
                </View>
                <StatsStrip
                  items={[
                    {
                      label: "Jami",
                      value: String(report.grand_commission),
                    },
                    {
                      label: "Qoldiq",
                      value: String(report.grand_remaining),
                      warn: Number(report.grand_remaining) > 0,
                    },
                  ]}
                />
              </View>
            ) : null
          }
          ListEmptyComponent={
            <EmptyState title="Komissiya yo‘q" hint="Hisobot bo‘sh" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={String(item.name)}
              meta={`${String(item.count)} bron · ${String(item.commission_total)} · qoldiq ${String(item.remaining)}`}
              badge={Number(item.remaining) > 0 ? "Qarz" : "To‘langan"}
              badgeTone={Number(item.remaining) > 0 ? "warn" : "success"}
              leading={<AvatarMark label={String(item.name)} />}
              onPress={() => {
                setPayId(Number(item.referrer_id));
                setPayAmount(String(item.remaining || ""));
              }}
            />
          )}
        />
      )}
    </View>
  );
}
