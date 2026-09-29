import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ListCard } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpen?: (target: string, id?: number) => void;
};

type NotifyItem = {
  key: string;
  kind: string;
  title: string;
  detail: string;
  pk?: number;
  url_name?: string;
  target?: string;
  target_id?: number;
};

function kindTone(
  kind: string
): "neutral" | "success" | "warn" | "danger" | "info" | "accent" {
  const k = kind.toLowerCase();
  if (k.includes("maint") || k.includes("stock")) return "warn";
  if (k.includes("arriv") || k.includes("depart")) return "accent";
  if (k.includes("overdue") || k.includes("folio")) return "danger";
  return "info";
}

export function NotificationsScreen({ onBack, onOpen }: Props) {
  const { fetchNotifications, dismissNotification } = useAuth();
  const [items, setItems] = useState<NotifyItem[]>([]);
  const [count, setCount] = useState(0);
  const [day, setDay] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const data = await fetchNotifications();
        setItems(data.items || []);
        setCount(data.count ?? (data.items || []).length);
        setDay(data.day ? String(data.day) : "");
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchNotifications]
  );

  useEffect(() => {
    load();
  }, [load]);

  async function onDismiss(key: string) {
    try {
      await dismissNotification(key);
      setItems((prev) => prev.filter((i) => i.key !== key));
      setCount((c) => Math.max(0, c - 1));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yopish xatosi");
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Operatsiya"
        title="Bildirishnomalar"
        subtitle={day ? `${count} · ${day}` : `${count} ta`}
        onBack={onBack}
      />
      {error ? (
        <Text style={[ui.error, { paddingHorizontal: space.lg }]}>{error}</Text>
      ) : null}
      {loading && items.length === 0 ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.key}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState
              title="Bo‘sh"
              hint="Bugun uchun ochiq bildirishnoma yo‘q"
            />
          }
          renderItem={({ item }) => (
            <ListCard
              title={item.title}
              meta={item.detail || item.kind}
              badge={item.kind}
              badgeTone={kindTone(item.kind)}
            >
              <View style={{ flexDirection: "row", gap: 8, marginTop: 10 }}>
                {item.target && onOpen ? (
                  <Pressable
                    style={ui.chip}
                    onPress={() =>
                      onOpen(item.target || "", item.target_id || item.pk)
                    }
                  >
                    <Text style={ui.chipText}>Ochish</Text>
                  </Pressable>
                ) : null}
                <Pressable style={ui.chip} onPress={() => onDismiss(item.key)}>
                  <Text style={ui.chipText}>Yopish</Text>
                </Pressable>
              </View>
            </ListCard>
          )}
        />
      )}
    </View>
  );
}
