import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ListCard } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

type AuditRow = {
  id: number;
  action: string;
  model?: string;
  object_id?: string;
  user?: string | null;
  created_at?: string | null;
  payload?: Record<string, unknown>;
};

function toneForAction(
  action: string
): "neutral" | "success" | "warn" | "danger" | "info" | "accent" {
  const a = action.toLowerCase();
  if (a.includes("void") || a.includes("cancel")) return "danger";
  if (a.includes("pay") || a.includes("check_in") || a.includes("done"))
    return "success";
  if (a.includes("approve") || a.includes("audit")) return "accent";
  if (a.includes("charge") || a.includes("expense")) return "warn";
  return "info";
}

function formatWhen(iso?: string | null) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16).replace("T", " ");
  }
}

export function AuditLogScreen({ onBack }: Props) {
  const { fetchAuditLog } = useAuth();
  const [items, setItems] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setItems(
          (await fetchAuditLog({
            action: filter.trim() || undefined,
            limit: 200,
          })) as AuditRow[]
        );
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchAuditLog, filter]
  );

  useEffect(() => {
    load();
  }, [load]);

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Hisobot"
        title="Audit log"
        subtitle="So‘nggi faoliyat"
        onBack={onBack}
      />
      <View style={styles.searchWrap}>
        <TextInput
          style={styles.search}
          placeholder="Filter: payment, check_in…"
          placeholderTextColor={colors.faint}
          autoCapitalize="none"
          value={filter}
          onChangeText={setFilter}
          onSubmitEditing={() => load(true)}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
      </View>
      {error ? <Text style={[ui.error, { padding: space.lg }]}>{error}</Text> : null}
      {loading && items.length === 0 ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => String(t.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          contentContainerStyle={ui.listPad}
          ListEmptyComponent={
            <EmptyState title="Yozuv yo‘q" hint="Filterni o‘zgartirib ko‘ring" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={item.action.replace(/_/g, " ")}
              meta={`${formatWhen(item.created_at)}${
                item.user ? ` · ${item.user}` : ""
              }${item.object_id ? ` · #${item.object_id}` : ""}`}
              badge={item.model || "event"}
              badgeTone={toneForAction(item.action)}
            >
              {item.payload && Object.keys(item.payload).length ? (
                <Text style={styles.payload} numberOfLines={2}>
                  {JSON.stringify(item.payload)}
                </Text>
              ) : null}
            </ListCard>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  searchWrap: {
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    paddingBottom: space.sm,
  },
  search: {
    ...ui.input,
    marginBottom: 0,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
  },
  payload: {
    marginTop: space.sm,
    color: colors.muted,
    fontSize: 12,
    fontFamily: fontUi,
    lineHeight: 16,
  },
});
