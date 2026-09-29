import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  StatsStrip,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";
import { sharePdfBase64 } from "../utils/sharePdf";

type Props = { onBack: () => void; mode: "expenses" | "pnl" | "profit"; year?: number; month?: number };

type Cat = { id: number; name: string };
type Vendor = { id: number; name: string };

function expenseTone(
  status: string
): "neutral" | "success" | "warn" | "danger" | "info" | "accent" {
  if (status === "paid") return "success";
  if (status === "approved") return "accent";
  if (status === "draft") return "warn";
  if (status === "rejected") return "danger";
  return "neutral";
}

export function FinanceScreen({ onBack, mode, year, month }: Props) {
  const {
    fetchExpenses,
    fetchPnl,
    fetchExpenseMeta,
    createExpense,
    approveExpense,
    payExpense,
    rejectExpense,
    reopenExpense,
    deleteExpense,
    createExpenseCategory,
    createExpenseVendor,
    fetchProfit,
    createProfitPartner,
    withdrawProfit,
    resetProfit,
    printPnl,
    printExpense,
  } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [pnl, setPnl] = useState<Record<string, unknown> | null>(null);
  const [profit, setProfit] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [categories, setCategories] = useState<Cat[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [vendorId, setVendorId] = useState<number | null>(null);
  const [newCatName, setNewCatName] = useState("");
  const [newVendorName, setNewVendorName] = useState("");
  const [showNewCat, setShowNewCat] = useState(false);
  const [showNewVendor, setShowNewVendor] = useState(false);
  const [busy, setBusy] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [expenseStatus, setExpenseStatus] = useState("");
  const [pnlYear, setPnlYear] = useState(
    () => year ?? new Date().getFullYear()
  );
  const [pnlMonth, setPnlMonth] = useState(
    () => month ?? new Date().getMonth() + 1
  );

  // Profit UI
  const [partnerName, setPartnerName] = useState("");
  const [partnerPct, setPartnerPct] = useState("");
  const [showPartnerForm, setShowPartnerForm] = useState(false);
  const [withdrawPartnerId, setWithdrawPartnerId] = useState<number | null>(
    null
  );
  const [withdrawAmount, setWithdrawAmount] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (mode === "expenses") {
        const [list, meta] = await Promise.all([
          fetchExpenses(expenseStatus),
          fetchExpenseMeta().catch(() => null),
        ]);
        setItems(list);
        const cats = (meta?.categories as Cat[]) || [];
        const vends = (meta?.vendors as Vendor[]) || [];
        setCategories(cats);
        setVendors(vends);
        if (!categoryId && cats[0]) setCategoryId(cats[0].id);
      } else if (mode === "pnl") {
        setPnl(await fetchPnl(pnlYear, pnlMonth));
      } else {
        setProfit(await fetchProfit());
      }
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [
    fetchExpenses,
    fetchExpenseMeta,
    fetchPnl,
    fetchProfit,
    mode,
    categoryId,
    year,
    month,
    pnlYear,
    pnlMonth,
    expenseStatus,
  ]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when mode/period/filter changes
  }, [mode, year, month, pnlYear, pnlMonth, expenseStatus]);

  async function submitExpense() {
    if (!title.trim() || !amount.trim() || !categoryId) {
      Alert.alert("Xato", "Sarlavha, summa va kategoriya kerak");
      return;
    }
    setBusy(true);
    try {
      await createExpense({
        title: title.trim(),
        amount: amount.trim(),
        category_id: categoryId,
        ...(vendorId ? { vendor_id: vendorId } : {}),
      });
      setTitle("");
      setAmount("");
      setCreating(false);
      await load();
      Alert.alert("OK", "Rasxod qo‘shildi (qoralama)");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onApprove(id: number) {
    try {
      await approveExpense(id);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function onPay(id: number) {
    try {
      await payExpense(id);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function doReject(id: number, reason: string) {
    try {
      await rejectExpense(id, reason);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  function onReject(id: number) {
    if (Platform.OS === "ios") {
      Alert.prompt(
        "Rad etish",
        "Sabab (ixtiyoriy)",
        (reason) => {
          void doReject(id, (reason || "").trim() || "Rad etildi");
        },
        "plain-text"
      );
    } else {
      Alert.alert("Rad etish", "Xarajat rad etilsinmi?", [
        { text: "Bekor", style: "cancel" },
        {
          text: "Rad etish",
          style: "destructive",
          onPress: () => void doReject(id, "Rad etildi"),
        },
      ]);
    }
  }

  async function onReopen(id: number) {
    try {
      await reopenExpense(id);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function onPrintPnl() {
    setPrinting(true);
    try {
      const file = await printPnl(pnlYear, pnlMonth);
      await sharePdfBase64(file.pdf_base64, file.filename || "pnl.pdf");
    } catch (e) {
      Alert.alert("PDF", e instanceof ApiError ? e.message : "Chop etish xatosi");
    } finally {
      setPrinting(false);
    }
  }

  async function onPrintExpense(id: number) {
    setPrinting(true);
    try {
      const file = await printExpense(id);
      await sharePdfBase64(
        file.pdf_base64,
        file.filename || `expense-${id}.pdf`
      );
    } catch (e) {
      Alert.alert("PDF", e instanceof ApiError ? e.message : "Chop etish xatosi");
    } finally {
      setPrinting(false);
    }
  }

  function onDelete(id: number) {
    Alert.alert("O‘chirish", "Xarajat o‘chirilsinmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "O‘chirish",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteExpense(id);
            await load();
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          }
        },
      },
    ]);
  }

  async function addCategory() {
    if (!newCatName.trim()) return;
    setBusy(true);
    try {
      const cat = await createExpenseCategory(newCatName.trim());
      setCategories((prev) => [
        ...prev,
        { id: Number(cat.id), name: String(cat.name) },
      ]);
      setCategoryId(Number(cat.id));
      setNewCatName("");
      setShowNewCat(false);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function addVendor() {
    if (!newVendorName.trim()) return;
    setBusy(true);
    try {
      const v = await createExpenseVendor({ name: newVendorName.trim() });
      setVendors((prev) => [
        ...prev,
        { id: Number(v.id), name: String(v.name) },
      ]);
      setVendorId(Number(v.id));
      setNewVendorName("");
      setShowNewVendor(false);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onCreatePartner() {
    if (!partnerName.trim()) return;
    setBusy(true);
    try {
      await createProfitPartner({
        name: partnerName.trim(),
        share_percent: partnerPct.trim() || "0",
      });
      setPartnerName("");
      setPartnerPct("");
      setShowPartnerForm(false);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onWithdraw() {
    if (!withdrawPartnerId || !withdrawAmount.trim()) return;
    setBusy(true);
    try {
      await withdrawProfit({
        partner_id: withdrawPartnerId,
        amount: withdrawAmount.trim(),
      });
      setWithdrawPartnerId(null);
      setWithdrawAmount("");
      await load();
      Alert.alert("OK", "Yechib olindi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  function onResetProfit() {
    Alert.alert(
      "Davrni yopish",
      "Foyda davri yopilib yangisi ochilsinmi?",
      [
        { text: "Bekor", style: "cancel" },
        {
          text: "Yopish",
          style: "destructive",
          onPress: async () => {
            try {
              await resetProfit();
              await load();
              Alert.alert("OK", "Yangi davr ochildi");
            } catch (e) {
              Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
            }
          },
        },
      ]
    );
  }

  if (mode === "pnl") {
    const data = (pnl?.pnl || {}) as Record<string, unknown>;
    const rows = Object.entries(data).slice(0, 24);
    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow="Hisobot"
          title="P&L"
          subtitle={pnl ? `${pnl.year}-${pnl.month}` : undefined}
          onBack={onBack}
          right={
            <Pressable
              style={({ pressed }) => [
                ui.copperBtn,
                pressed && { opacity: 0.85 },
                printing && { opacity: 0.5 },
              ]}
              onPress={onPrintPnl}
              disabled={printing}
            >
              <Text style={ui.copperBtnText}>{printing ? "…" : "PDF"}</Text>
            </Pressable>
          }
        />
        {loading && !pnl ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : (
          <ScrollView
            contentContainerStyle={ui.listPad}
            showsVerticalScrollIndicator={false}
          >
            <View
              style={{
                flexDirection: "row",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: space.md,
              }}
            >
              {[new Date().getFullYear() - 1, new Date().getFullYear(), new Date().getFullYear() + 1].map((y) => (
                  <Pressable
                    key={y}
                    style={[ui.chip, y === pnlYear && ui.chipOn]}
                    onPress={() => setPnlYear(y)}
                  >
                    <Text style={[ui.chipText, y === pnlYear && ui.chipTextOn]}>
                      {y}
                    </Text>
                  </Pressable>
              ))}
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <Pressable
                  key={m}
                  style={[ui.chip, m === pnlMonth && ui.chipOn]}
                  onPress={() => setPnlMonth(m)}
                >
                  <Text style={[ui.chipText, m === pnlMonth && ui.chipTextOn]}>
                    {m}
                  </Text>
                </Pressable>
              ))}
            </View>
            {rows.length === 0 ? (
              <EmptyState title="Ma’lumot yo‘q" />
            ) : (
              rows.map(([k, v]) => (
                <ListCard
                  key={k}
                  title={
                    typeof v === "object" ? JSON.stringify(v) : String(v)
                  }
                  meta={k.replace(/_/g, " ")}
                />
              ))
            )}
          </ScrollView>
        )}
      </View>
    );
  }

  if (mode === "profit") {
    const rows = (profit?.rows as Record<string, unknown>[]) || [];
    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow="Moliya"
          title="Foyda ulushi"
          subtitle={
            profit
              ? `${String(profit.start || "")} → ${String(profit.end || "…")}`
              : "Hamkorlar ledger"
          }
          onBack={onBack}
          right={
            <Pressable
              style={({ pressed }) => [
                ui.copperBtn,
                pressed && { opacity: 0.85 },
              ]}
              onPress={() => setShowPartnerForm((v) => !v)}
            >
              <Text style={ui.copperBtnText}>
                {showPartnerForm ? "Yopish" : "+ Hamkor"}
              </Text>
            </Pressable>
          }
        />

        {profit ? (
          <View style={{ marginTop: space.sm }}>
            <StatsStrip
              items={[
                { label: "Sof", value: String(profit.net ?? "—") },
                {
                  label: "Taqsim",
                  value: String(profit.distributable ?? "—"),
                },
                {
                  label: "Qayta",
                  value: String(profit.reinvestment ?? "—"),
                },
              ]}
            />
          </View>
        ) : null}

        <View
          style={{
            paddingHorizontal: space.lg,
            paddingTop: space.md,
            gap: 8,
          }}
        >
          <PrimaryButton
            label="Davrni yopish / reset"
            onPress={onResetProfit}
            tone="ghost"
          />
        </View>

        {showPartnerForm ? (
          <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
            <FormCard>
              <FieldLabel>Hamkor nomi</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="Ism"
                placeholderTextColor={colors.faint}
                value={partnerName}
                onChangeText={setPartnerName}
              />
              <FieldLabel>Ulush %</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="50"
                placeholderTextColor={colors.faint}
                keyboardType="decimal-pad"
                value={partnerPct}
                onChangeText={setPartnerPct}
              />
              <PrimaryButton
                label="Qo‘shish"
                onPress={onCreatePartner}
                loading={busy}
              />
            </FormCard>
          </View>
        ) : null}

        {withdrawPartnerId != null ? (
          <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
            <FormCard>
              <FieldLabel>Yechib olish summasi</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="0.00"
                placeholderTextColor={colors.faint}
                keyboardType="decimal-pad"
                value={withdrawAmount}
                onChangeText={setWithdrawAmount}
              />
              <PrimaryButton
                label="Yechib olish"
                onPress={onWithdraw}
                loading={busy}
              />
              <PrimaryButton
                label="Bekor"
                onPress={() => setWithdrawPartnerId(null)}
                tone="ghost"
              />
            </FormCard>
          </View>
        ) : null}

        {loading && !profit ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : (
          <FlatList
            data={rows}
            keyExtractor={(i) => String(i.partner_id)}
            contentContainerStyle={ui.listPad}
            refreshControl={
              <RefreshControl
                refreshing={loading}
                onRefresh={load}
                tintColor={colors.accent}
              />
            }
            ListEmptyComponent={
              <EmptyState
                title="Hamkor yo‘q"
                hint="Yangi hamkor qo‘shing"
              />
            }
            renderItem={({ item }) => (
              <ListCard
                title={String(item.name)}
                meta={`Ulush ${String(item.share_percent)}% · huquq ${String(
                  item.entitled
                )} · olingan ${String(item.withdrawn)}`}
                badge={String(item.remaining)}
                badgeTone={
                  Number(item.remaining) > 0 ? "warn" : "success"
                }
                onPress={() => {
                  setWithdrawPartnerId(Number(item.partner_id));
                  setWithdrawAmount(String(item.remaining || ""));
                }}
              />
            )}
          />
        )}
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Moliya"
        title="Xarajatlar"
        subtitle={`${items.length} yozuv`}
        onBack={onBack}
        right={
          <Pressable
            style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
            onPress={() => setCreating((v) => !v)}
          >
            <Text style={ui.copperBtnText}>
              {creating ? "Yopish" : "+ Yangi"}
            </Text>
          </Pressable>
        }
      />
      {creating ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>Sarlavha</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Masalan: Ofis"
              placeholderTextColor={colors.faint}
              value={title}
              onChangeText={setTitle}
            />
            <FieldLabel>Summa</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="50000"
              placeholderTextColor={colors.faint}
              keyboardType="decimal-pad"
              value={amount}
              onChangeText={setAmount}
            />
            <FieldLabel>Kategoriya</FieldLabel>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
                {categories.map((c) => (
                  <Pressable
                    key={c.id}
                    style={[ui.chip, categoryId === c.id && ui.chipOn]}
                    onPress={() => setCategoryId(c.id)}
                  >
                    <Text
                      style={[
                        ui.chipText,
                        categoryId === c.id && ui.chipTextOn,
                      ]}
                    >
                      {c.name}
                    </Text>
                  </Pressable>
                ))}
                <Pressable
                  style={ui.chip}
                  onPress={() => setShowNewCat((v) => !v)}
                >
                  <Text style={ui.chipText}>+ Kategoriya</Text>
                </Pressable>
              </View>
            </ScrollView>
            {showNewCat || categories.length === 0 ? (
              <View style={{ marginBottom: 8 }}>
                <TextInput
                  style={ui.input}
                  placeholder="Yangi kategoriya"
                  placeholderTextColor={colors.faint}
                  value={newCatName}
                  onChangeText={setNewCatName}
                />
                <PrimaryButton
                  label="Kategoriya qo‘shish"
                  onPress={addCategory}
                  loading={busy}
                  tone="ghost"
                />
              </View>
            ) : null}

            <FieldLabel>Vendor</FieldLabel>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
                {vendors.map((v) => (
                  <Pressable
                    key={v.id}
                    style={[ui.chip, vendorId === v.id && ui.chipOn]}
                    onPress={() =>
                      setVendorId(vendorId === v.id ? null : v.id)
                    }
                  >
                    <Text
                      style={[
                        ui.chipText,
                        vendorId === v.id && ui.chipTextOn,
                      ]}
                    >
                      {v.name}
                    </Text>
                  </Pressable>
                ))}
                <Pressable
                  style={ui.chip}
                  onPress={() => setShowNewVendor((v) => !v)}
                >
                  <Text style={ui.chipText}>+ Vendor</Text>
                </Pressable>
              </View>
            </ScrollView>
            {showNewVendor || vendors.length === 0 ? (
              <View style={{ marginBottom: 8 }}>
                <TextInput
                  style={ui.input}
                  placeholder="Vendor nomi"
                  placeholderTextColor={colors.faint}
                  value={newVendorName}
                  onChangeText={setNewVendorName}
                />
                <PrimaryButton
                  label="Vendor qo‘shish"
                  onPress={addVendor}
                  loading={busy}
                  tone="ghost"
                />
              </View>
            ) : null}

            <PrimaryButton
              label="Saqlash"
              onPress={submitExpense}
              loading={busy}
            />
          </FormCard>
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
            <RefreshControl
              refreshing={loading}
              onRefresh={load}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Xarajat yo‘q" hint="Yangi rasxod qo‘shing" />
          }
          ListHeaderComponent={
            <View
              style={{
                flexDirection: "row",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: space.sm,
              }}
            >
              {[
                ["", "Hammasi"],
                ["draft", "Qoralama"],
                ["approved", "Tasdiq"],
                ["paid", "To‘langan"],
                ["rejected", "Rad"],
              ].map(([id, label]) => (
                <Pressable
                  key={id || "all"}
                  style={[ui.chip, expenseStatus === id && ui.chipOn]}
                  onPress={() => setExpenseStatus(id)}
                >
                  <Text
                    style={[
                      ui.chipText,
                      expenseStatus === id && ui.chipTextOn,
                    ]}
                  >
                    {label}
                  </Text>
                </Pressable>
              ))}
            </View>
          }
          renderItem={({ item }) => {
            const st = String(item.status);
            return (
              <ListCard
                title={String(item.title)}
                meta={`${String(item.expense_date)} · ${
                  item.category ? `${item.category} · ` : ""
                }${String(item.amount)}`}
                badge={st}
                badgeTone={expenseTone(st)}
              >
                <View
                  style={{
                    flexDirection: "row",
                    flexWrap: "wrap",
                    gap: 8,
                    marginTop: 10,
                  }}
                >
                  {st === "draft" ? (
                    <Pressable
                      style={ui.chip}
                      onPress={() => onApprove(Number(item.id))}
                    >
                      <Text style={ui.chipText}>Tasdiqlash</Text>
                    </Pressable>
                  ) : null}
                  {st === "approved" ? (
                    <Pressable
                      style={[ui.chip, ui.chipOn]}
                      onPress={() => onPay(Number(item.id))}
                    >
                      <Text style={[ui.chipText, ui.chipTextOn]}>
                        To‘landi
                      </Text>
                    </Pressable>
                  ) : null}
                  {st === "draft" || st === "approved" ? (
                    <Pressable
                      style={ui.chip}
                      onPress={() => onReject(Number(item.id))}
                    >
                      <Text style={ui.chipText}>Rad</Text>
                    </Pressable>
                  ) : null}
                  {st === "rejected" || st === "paid" ? (
                    <Pressable
                      style={ui.chip}
                      onPress={() => onReopen(Number(item.id))}
                    >
                      <Text style={ui.chipText}>Qayta ochish</Text>
                    </Pressable>
                  ) : null}
                  {st === "draft" || st === "rejected" ? (
                    <Pressable
                      style={ui.chip}
                      onPress={() => onDelete(Number(item.id))}
                    >
                      <Text style={ui.chipText}>O‘chirish</Text>
                    </Pressable>
                  ) : null}
                  <Pressable
                    style={ui.chip}
                    onPress={() => onPrintExpense(Number(item.id))}
                    disabled={printing}
                  >
                    <Text style={ui.chipText}>PDF</Text>
                  </Pressable>
                </View>
              </ListCard>
            );
          }}
        />
      )}
    </View>
  );
}
