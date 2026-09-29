import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
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
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";
import { sharePdfBase64 } from "../utils/sharePdf";

type Props = { onBack: () => void };

function statusTone(
  status: string
): "neutral" | "success" | "warn" | "danger" | "info" | "accent" {
  const s = status.toLowerCase();
  if (s === "paid" || s === "closed") return "success";
  if (s === "open" || s === "partial") return "warn";
  if (s === "overdue") return "danger";
  return "neutral";
}

export function CityLedgerScreen({ onBack }: Props) {
  const { fetchCityLedger, fetchCityLedgerDetail, payCityLedger } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [paying, setPaying] = useState(false);
  const [amount, setAmount] = useState("");
  const [sharing, setSharing] = useState(false);

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

  async function openDetail(id: number) {
    setDetailLoading(true);
    try {
      const d = await fetchCityLedgerDetail(id);
      setDetail(d);
      setAmount(String(d.balance || ""));
      setPaying(false);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setDetailLoading(false);
    }
  }

  async function submitPay() {
    if (!detail || !amount.trim()) return;
    try {
      await payCityLedger(Number(detail.id), amount.trim());
      setPaying(false);
      setAmount("");
      await openDetail(Number(detail.id));
      await load();
      Alert.alert("City ledger", "To‘lov yozildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function sharePdf() {
    if (!detail) return;
    setSharing(true);
    try {
      const d = await fetchCityLedgerDetail(Number(detail.id), true);
      const b64 = String(d.pdf_base64 || "");
      if (!b64) {
        Alert.alert("PDF", "PDF mavjud emas");
        return;
      }
      await sharePdfBase64(
        b64,
        String(d.filename || `${detail.code || "invoice"}.pdf`)
      );
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setSharing(false);
    }
  }

  if (detail) {
    const company = detail.company as { id?: number; name?: string } | string;
    const companyName =
      typeof company === "object" ? String(company?.name || "") : String(company || "");
    const lines = (detail.lines as Record<string, unknown>[]) || [];
    const payments = (detail.payments as Record<string, unknown>[]) || [];

    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow="City ledger"
          title={String(detail.code)}
          subtitle={`${companyName} · ${String(detail.status)}`}
          onBack={() => setDetail(null)}
          right={
            <Pressable
              style={({ pressed }) => [
                ui.copperBtn,
                pressed && { opacity: 0.85 },
              ]}
              onPress={sharePdf}
              disabled={sharing}
            >
              <Text style={ui.copperBtnText}>
                {sharing ? "…" : "PDF"}
              </Text>
            </Pressable>
          }
        />
        {detailLoading ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : (
          <ScrollView
            contentContainerStyle={ui.listPad}
            showsVerticalScrollIndicator={false}
          >
            <ListCard
              title={`Jami ${String(detail.total)}`}
              meta={`Qoldiq ${String(detail.balance)}${
                detail.due_date ? ` · muddat ${detail.due_date}` : ""
              }`}
              badge={String(detail.status)}
              badgeTone={statusTone(String(detail.status))}
            />

            <View
              style={{
                flexDirection: "row",
                gap: 8,
                marginBottom: space.md,
              }}
            >
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  label={paying ? "Yopish" : "To‘lash"}
                  onPress={() => setPaying((v) => !v)}
                />
              </View>
            </View>

            {paying ? (
              <FormCard>
                <FieldLabel>To‘lov summasi</FieldLabel>
                <TextInput
                  style={ui.input}
                  value={amount}
                  onChangeText={setAmount}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor={colors.faint}
                />
                <PrimaryButton label="To‘lash" onPress={submitPay} />
              </FormCard>
            ) : null}

            <Text style={ui.section}>Qatorlar ({lines.length})</Text>
            {lines.length === 0 ? (
              <EmptyState title="Qator yo‘q" />
            ) : (
              lines.map((ln) => (
                <ListCard
                  key={String(ln.id)}
                  title={String(ln.description)}
                  meta={String(ln.amount)}
                />
              ))
            )}

            <Text style={ui.section}>To‘lovlar ({payments.length})</Text>
            {payments.length === 0 ? (
              <EmptyState title="To‘lov yo‘q" />
            ) : (
              payments.map((p) => (
                <ListCard
                  key={String(p.id)}
                  title={String(p.amount)}
                  meta={`${String(p.method || "")}${
                    p.paid_at ? ` · ${String(p.paid_at).slice(0, 10)}` : ""
                  }${p.note ? ` · ${p.note}` : ""}`}
                  badgeTone="success"
                  badge="Paid"
                />
              ))
            )}
          </ScrollView>
        )}
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Moliya"
        title="City ledger"
        subtitle={
          items.length
            ? `${items.length} ochiq hisob-faktura`
            : "Korporativ debitorlik"
        }
        onBack={onBack}
      />
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
            <EmptyState
              title="Ochiq hisob-faktura yo‘q"
              hint="Barcha city ledger yozuvlari yopilgan"
            />
          }
          renderItem={({ item }) => (
            <ListCard
              title={`${String(item.code)} · ${String(item.company)}`}
              meta={`Jami ${String(item.total)} · qoldiq ${String(item.balance)}`}
              badge={String(item.status)}
              badgeTone={statusTone(String(item.status))}
              leading={
                <AvatarMark label={String(item.company || item.code)} />
              }
              onPress={() => openDetail(Number(item.id))}
            />
          )}
        />
      )}
    </View>
  );
}
