import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../auth/AuthContext";
import { MenuRow } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = {
  onOpenGuests: () => void;
  onOpenInquiries: () => void;
  onOpenCash: () => void;
  onNewBooking: () => void;
  onOpenFlash: () => void;
  onOpenMaintenance: () => void;
  onOpenCompanies: () => void;
  onOpenCityLedger: () => void;
  onOpenGroups: () => void;
  onOpenNightAudit: () => void;
  onOpenExpenses: () => void;
  onOpenPnl: () => void;
  onOpenInventory: () => void;
  onOpenReferrers: () => void;
  onOpenHr: () => void;
};

export function MoreScreen({
  onOpenGuests,
  onOpenInquiries,
  onOpenCash,
  onNewBooking,
  onOpenFlash,
  onOpenMaintenance,
  onOpenCompanies,
  onOpenCityLedger,
  onOpenGroups,
  onOpenNightAudit,
  onOpenExpenses,
  onOpenPnl,
  onOpenInventory,
  onOpenReferrers,
  onOpenHr,
}: Props) {
  const { me, logout } = useAuth();
  const canFront =
    me?.permissions?.front_office === true ||
    ["admin", "receptionist"].includes(me?.role || "");
  const canCash =
    me?.permissions?.cash === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");
  const canDash =
    me?.permissions?.dashboard === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");
  const canMaint =
    me?.permissions?.maintenance === true ||
    ["admin", "manager", "receptionist"].includes(me?.role || "");
  const canFinance =
    me?.permissions?.city_ledger === true ||
    me?.permissions?.expenses === true ||
    me?.permissions?.pnl === true ||
    ["admin", "accountant", "manager"].includes(me?.role || "");
  const canAudit =
    me?.permissions?.audit === true ||
    ["admin", "manager", "accountant"].includes(me?.role || "");
  const canInv =
    me?.permissions?.inventory === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");
  const canHr =
    me?.permissions?.hr === true || ["admin", "hr"].includes(me?.role || "");

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Yana"
        title={me?.user.full_name || "Profil"}
        subtitle={`${me?.hotel?.name || me?.tenant.name || ""} · ${me?.role || ""}`}
      />
      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.group}>Front desk</Text>
        {canFront ? (
          <MenuRow title="Yangi bron" hint="Oldindan bron" onPress={onNewBooking} />
        ) : null}
        {canFront ? (
          <MenuRow title="Mehmonlar" hint="Qidiruv / hujjat" onPress={onOpenGuests} />
        ) : null}
        {canFront ? (
          <MenuRow title="So‘rovlar" hint="Tasdiqlash" onPress={onOpenInquiries} />
        ) : null}
        {canFront ? (
          <MenuRow title="Guruhlar" hint="Ko‘p xonali bronlar" onPress={onOpenGroups} />
        ) : null}
        {canFront ? (
          <MenuRow title="Kompaniyalar" hint="Korporativ mijozlar" onPress={onOpenCompanies} />
        ) : null}
        {canFront ? (
          <MenuRow
            title="Yo‘naltiruvchilar"
            hint="Agentlar / komissiya"
            onPress={onOpenReferrers}
          />
        ) : null}
        {canCash ? (
          <MenuRow title="Kassa smena" hint="Ochish / yopish" onPress={onOpenCash} />
        ) : null}

        <Text style={styles.group}>Operatsiya</Text>
        {canInv ? (
          <MenuRow title="Ombor" hint="Kirim / chiqim / kam qoldiq" onPress={onOpenInventory} />
        ) : null}
        {canMaint ? (
          <MenuRow title="Ta’mir" hint="Arizalar" onPress={onOpenMaintenance} />
        ) : null}
        {canDash ? (
          <MenuRow title="Kunlik flash" hint="OCC · ADR" onPress={onOpenFlash} />
        ) : null}
        {canAudit ? (
          <MenuRow title="Kun yopish" hint="Night audit" onPress={onOpenNightAudit} />
        ) : null}

        <Text style={styles.group}>Moliya</Text>
        {canFinance ? (
          <MenuRow title="City ledger" hint="Kompaniya qarzlari" onPress={onOpenCityLedger} />
        ) : null}
        {canFinance ? (
          <MenuRow title="Xarajatlar" hint="Rasxodlar ro‘yxati" onPress={onOpenExpenses} />
        ) : null}
        {canFinance ? (
          <MenuRow title="P&L" hint="Oylik foyda" onPress={onOpenPnl} />
        ) : null}

        {canHr ? (
          <>
            <Text style={styles.group}>HR</Text>
            <MenuRow title="Xodimlar" hint="Oylik / avans" onPress={onOpenHr} />
          </>
        ) : null}

        <Pressable style={styles.logout} onPress={logout}>
          <Text style={styles.logoutText}>Chiqish</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: {
    paddingHorizontal: space.xl,
    paddingTop: space.md,
    paddingBottom: 110,
  },
  group: {
    ...ui.section,
    marginTop: space.xl,
    marginBottom: space.sm,
  },
  logout: {
    marginTop: space.xxl,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
    backgroundColor: colors.night,
  },
  logoutText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 15,
  },
});
