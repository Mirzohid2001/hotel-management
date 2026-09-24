import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontDisplay, space, ui } from "../ui/theme";

type Props = { onBack: () => void; mode: "expenses" | "pnl" };

export function FinanceScreen({ onBack, mode }: Props) {
  const { fetchExpenses, fetchPnl } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [pnl, setPnl] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (mode === "expenses") setItems(await fetchExpenses());
      else setPnl(await fetchPnl());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchExpenses, fetchPnl, mode]);

  useEffect(() => {
    load();
  }, [load]);

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
        />
        {loading && !pnl ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : (
          <ScrollView contentContainerStyle={ui.listPad}>
            {rows.map(([k, v]) => (
              <View key={k} style={ui.rowItem}>
                <Text style={ui.rowMeta}>{k}</Text>
                <Text
                  style={{
                    marginTop: 4,
                    fontSize: 18,
                    fontWeight: "700",
                    fontFamily: fontDisplay,
                    color: colors.ink,
                  }}
                >
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </Text>
              </View>
            ))}
          </ScrollView>
        )}
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader eyebrow="Moliya" title="Xarajatlar" onBack={onBack} />
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
          ListEmptyComponent={<Text style={ui.empty}>Xarajat yo‘q</Text>}
          renderItem={({ item }) => (
            <View style={ui.rowItem}>
              <Text style={ui.rowTitle}>{String(item.title)}</Text>
              <Text style={ui.rowMeta}>
                {String(item.expense_date)} · {String(item.amount)} ·{" "}
                {String(item.status)}
                {item.category ? ` · ${item.category}` : ""}
              </Text>
            </View>
          )}
        />
      )}
    </View>
  );
}
