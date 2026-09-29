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
import {
  ActionCard,
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  SegmentedTabs,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };
type Tab = "employees" | "advances";

export function HrScreen({ onBack }: Props) {
  const {
    fetchEmployees,
    payEmployee,
    advanceEmployee,
    createEmployee,
    fetchPayroll,
    generatePayroll,
    finalizePayroll,
    payAllPayroll,
    fetchHrAdvances,
    settleHrAdvance,
  } = useAuth();
  const [tab, setTab] = useState<Tab>("employees");
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [advances, setAdvances] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [mode, setMode] = useState<"pay" | "advance">("pay");
  const [amount, setAmount] = useState("");
  const [days, setDays] = useState("1");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [fullName, setFullName] = useState("");
  const [salary, setSalary] = useState("");
  const [salaryType, setSalaryType] = useState<"monthly" | "daily">("monthly");
  const [payroll, setPayroll] = useState<Record<string, unknown> | null>(null);

  const loadEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const [emps, pay] = await Promise.all([
        fetchEmployees(),
        fetchPayroll().catch(() => null),
      ]);
      setItems(emps);
      setPayroll(pay);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchEmployees, fetchPayroll]);

  const loadAdvances = useCallback(async () => {
    setLoading(true);
    try {
      setAdvances(await fetchHrAdvances());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchHrAdvances]);

  useEffect(() => {
    if (tab === "employees") loadEmployees();
    else loadAdvances();
  }, [tab, loadEmployees, loadAdvances]);

  async function onCreateEmp() {
    if (!fullName.trim()) return;
    setBusy(true);
    try {
      await createEmployee({
        full_name: fullName.trim(),
        salary_type: salaryType,
        base_salary: salary || "0",
      });
      setCreating(false);
      setFullName("");
      setSalary("");
      await loadEmployees();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onPayrollGen() {
    setBusy(true);
    try {
      await generatePayroll();
      await loadEmployees();
      Alert.alert("OK", "Oylik davr yaratildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onPayrollFinalize() {
    const id = (payroll?.period as { id?: number } | null)?.id;
    if (!id) {
      Alert.alert("HR", "Avval davr yarating");
      return;
    }
    setBusy(true);
    try {
      await finalizePayroll(id);
      await loadEmployees();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onPayrollPayAll() {
    setBusy(true);
    try {
      const r = await payAllPayroll();
      await loadEmployees();
      Alert.alert("OK", `To‘landi: ${String(r.paid_count ?? 0)}`);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    if (!selected?.id) return;
    setBusy(true);
    try {
      if (mode === "advance") {
        if (!amount.trim()) return;
        await advanceEmployee(Number(selected.id), amount.trim());
        Alert.alert("HR", "Avans berildi");
      } else {
        await payEmployee(Number(selected.id), {
          days: selected.is_daily ? Number(days) || 1 : undefined,
        });
        Alert.alert("HR", "To‘landi");
      }
      setSelected(null);
      setAmount("");
      await loadEmployees();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onSettleAdvance(id: number) {
    setBusy(true);
    try {
      await settleHrAdvance(id);
      await loadAdvances();
      Alert.alert("HR", "Avans yopildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  const periodStatus = payroll?.exists
    ? String((payroll.period as { status?: string })?.status || "")
    : "yo‘q";

  const tabs: { id: Tab; label: string }[] = [
    { id: "employees", label: "Xodimlar" },
    { id: "advances", label: "Avanslar" },
  ];

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="HR"
        title="Xodimlar"
        subtitle={
          tab === "employees"
            ? `${items.length} kishi · oylik / avans`
            : `${advances.length} ochiq avans`
        }
        onBack={onBack}
        right={
          tab === "employees" ? (
            <Pressable
              style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
              onPress={() => setCreating((v) => !v)}
            >
              <Text style={ui.copperBtnText}>
                {creating ? "Yopish" : "+ Yangi"}
              </Text>
            </Pressable>
          ) : null
        }
      />

      <View style={styles.pad}>
        <SegmentedTabs tabs={tabs} value={tab} onChange={setTab} />
      </View>

      {tab === "employees" && creating ? (
        <View style={styles.pad}>
          <FormCard>
            <FieldLabel>To‘liq ism</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Ali Valiyev"
              placeholderTextColor={colors.faint}
              value={fullName}
              onChangeText={setFullName}
            />
            <FieldLabel>Stavka</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="3000000"
              placeholderTextColor={colors.faint}
              value={salary}
              onChangeText={setSalary}
              keyboardType="decimal-pad"
            />
            <View style={styles.flags}>
              <Pressable
                style={[ui.chip, salaryType === "monthly" && ui.chipOn]}
                onPress={() => setSalaryType("monthly")}
              >
                <Text
                  style={[
                    ui.chipText,
                    salaryType === "monthly" && ui.chipTextOn,
                  ]}
                >
                  Oylik
                </Text>
              </Pressable>
              <Pressable
                style={[ui.chip, salaryType === "daily" && ui.chipOn]}
                onPress={() => setSalaryType("daily")}
              >
                <Text
                  style={[ui.chipText, salaryType === "daily" && ui.chipTextOn]}
                >
                  Kunlik
                </Text>
              </Pressable>
            </View>
            <PrimaryButton
              label="Saqlash"
              onPress={onCreateEmp}
              loading={busy}
            />
          </FormCard>
        </View>
      ) : null}

      {tab === "employees" ? (
        <View style={styles.pad}>
          <Text style={ui.section}>
            Oylik {payroll ? `${payroll.year}-${payroll.month}` : ""} ·{" "}
            {periodStatus}
          </Text>
          <View style={{ gap: space.sm }}>
            <ActionCard
              title="Generate"
              hint="Oylik davr yaratish"
              cta="Ishga"
              busy={busy}
              onPress={onPayrollGen}
            />
            <ActionCard
              title="Finalize"
              hint="Davrni yakunlash"
              cta="OK"
              busy={busy}
              onPress={onPayrollFinalize}
            />
            <ActionCard
              title="Pay all"
              hint="Barcha to‘lovlarni yopish"
              cta="To‘lash"
              tone="accent"
              busy={busy}
              onPress={onPayrollPayAll}
            />
          </View>
        </View>
      ) : null}

      {tab === "employees" && selected ? (
        <View style={styles.pad}>
          <FormCard>
            <Text style={ui.rowTitle}>{String(selected.full_name)}</Text>
            <Text style={[ui.rowMeta, { marginBottom: 8 }]}>
              {selected.is_daily ? "Kunlik" : "Oylik"} · stavka{" "}
              {String(selected.base_salary)} · avans{" "}
              {String(selected.open_advance)}
            </Text>
            <View style={styles.flags}>
              <Pressable
                style={[ui.chip, mode === "pay" && ui.chipOn]}
                onPress={() => setMode("pay")}
              >
                <Text
                  style={[ui.chipText, mode === "pay" && ui.chipTextOn]}
                >
                  To‘lash
                </Text>
              </Pressable>
              <Pressable
                style={[ui.chip, mode === "advance" && ui.chipOn]}
                onPress={() => setMode("advance")}
              >
                <Text
                  style={[ui.chipText, mode === "advance" && ui.chipTextOn]}
                >
                  Avans
                </Text>
              </Pressable>
            </View>
            {mode === "pay" && selected.is_daily ? (
              <>
                <FieldLabel>Kunlar</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="1"
                  value={days}
                  onChangeText={setDays}
                  keyboardType="number-pad"
                  placeholderTextColor={colors.faint}
                />
              </>
            ) : null}
            {mode === "advance" ? (
              <>
                <FieldLabel>Avans summasi</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="Summa"
                  value={amount}
                  onChangeText={setAmount}
                  keyboardType="decimal-pad"
                  placeholderTextColor={colors.faint}
                />
              </>
            ) : null}
            <View style={styles.rowBtns}>
              <Pressable style={ui.copperBtn} onPress={() => setSelected(null)}>
                <Text style={ui.copperBtnText}>Bekor</Text>
              </Pressable>
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  label={mode === "pay" ? "To‘lash" : "Avans berish"}
                  onPress={onSubmit}
                  loading={busy}
                />
              </View>
            </View>
          </FormCard>
        </View>
      ) : null}

      {loading ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 24 }} />
      ) : tab === "employees" ? (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={loadEmployees}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Xodim yo‘q" hint="Yuqoridan qo‘shing" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={String(item.full_name)}
              meta={`${String(item.position || "—")} · ${
                item.is_daily ? "kunlik" : "oylik"
              } ${String(item.base_salary)}`}
              badge={
                Number(item.open_advance) > 0
                  ? `Avans ${String(item.open_advance)}`
                  : item.is_daily
                    ? "Kunlik"
                    : "Oylik"
              }
              badgeTone={Number(item.open_advance) > 0 ? "warn" : "accent"}
              leading={
                <AvatarMark label={String(item.full_name || "?")} />
              }
              onPress={() => setSelected(item)}
            />
          )}
        />
      ) : (
        <FlatList
          data={advances}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={loadAdvances}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Ochiq avans yo‘q" hint="Hammasi yopilgan" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={String(item.employee || "—")}
              meta={`Summa ${String(item.amount)} · ochiq ${String(item.open_amount)}${
                item.advance_date ? ` · ${String(item.advance_date)}` : ""
              }`}
              badge={String(item.open_amount)}
              badgeTone="warn"
              leading={
                <AvatarMark label={String(item.employee || "?")} />
              }
            >
              <View style={{ marginTop: space.sm }}>
                <PrimaryButton
                  label="Yopish"
                  onPress={() => onSettleAdvance(Number(item.id))}
                  loading={busy}
                  tone="ink"
                />
              </View>
            </ListCard>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.md },
  flags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: space.sm,
  },
  rowBtns: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    marginTop: space.sm,
  },
});
