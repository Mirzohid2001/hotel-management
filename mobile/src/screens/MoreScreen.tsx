import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../auth/AuthContext";
import { MenuRow, MenuSection } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

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
  onOpenProfit: () => void;
  onOpenFx: () => void;
  onOpenInventory: () => void;
  onOpenReferrers: () => void;
  onOpenHr: () => void;
  onOpenSetup: () => void;
  onOpenStaff: () => void;
  onOpenAudit: () => void;
  onOpenExports: () => void;
  onOpenNotifications: () => void;
  onOpenMinibar: () => void;
  onOpenBronlar: () => void;
  onOpenDashboard: () => void;
  onOpenServices: () => void;
  onOpenReportsHistory: () => void;
  onOpenProfile: () => void;
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
  onOpenProfit,
  onOpenFx,
  onOpenInventory,
  onOpenReferrers,
  onOpenHr,
  onOpenSetup,
  onOpenStaff,
  onOpenAudit,
  onOpenExports,
  onOpenNotifications,
  onOpenMinibar,
  onOpenBronlar,
  onOpenDashboard,
  onOpenServices,
  onOpenReportsHistory,
  onOpenProfile,
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
  const canStaff = me?.permissions?.staff === true || me?.role === "admin";
  const canExport =
    me?.permissions?.pnl === true ||
    me?.permissions?.audit === true ||
    ["admin", "accountant"].includes(me?.role || "");
  const canSetup = me?.role === "admin" || me?.role === "manager";

  const frontItems = [
    canFront && {
      title: "Yangi bron",
      hint: "Oldindan bron yaratish",
      mark: "＋",
      onPress: onNewBooking,
    },
    canFront && {
      title: "Bronlar",
      hint: "Period · status · jami",
      mark: "B",
      onPress: onOpenBronlar,
    },
    canFront && {
      title: "Minibar tez",
      hint: "Xona raqami bilan sotish",
      mark: "⌂",
      onPress: onOpenMinibar,
    },
    canFront && {
      title: "Xizmatlar",
      hint: "Buyurtma · katalog",
      mark: "S",
      onPress: onOpenServices,
    },
    canFront && {
      title: "Mehmonlar",
      hint: "Qidiruv va hujjatlar",
      mark: "M",
      onPress: onOpenGuests,
    },
    canFront && {
      title: "So‘rovlar",
      hint: "Tasdiqlash kerak",
      mark: "S",
      onPress: onOpenInquiries,
    },
    canFront && {
      title: "Guruhlar",
      hint: "Ko‘p xonali bronlar",
      mark: "G",
      onPress: onOpenGroups,
    },
    canFront && {
      title: "Kompaniyalar",
      hint: "Korporativ mijozlar",
      mark: "K",
      onPress: onOpenCompanies,
    },
    canFront && {
      title: "Yo‘naltiruvchilar",
      hint: "Agentlar · komissiya",
      mark: "Y",
      onPress: onOpenReferrers,
    },
    canCash && {
      title: "Kassa smena",
      hint: "Ochish / yopish",
      mark: "₸",
      onPress: onOpenCash,
    },
  ].filter(Boolean) as {
    title: string;
    hint: string;
    mark: string;
    onPress: () => void;
  }[];

  const opsItems = [
    {
      title: "Bildirishnomalar",
      hint: "Bugungi eslatmalar",
      mark: "!",
      onPress: onOpenNotifications,
    },
    canDash && {
      title: "Dashboard",
      hint: "OCC · ADR · ops",
      mark: "D",
      onPress: onOpenDashboard,
    },
    canDash && {
      title: "Hisobotlar tarixi",
      hint: "Oy · flash · P&L",
      mark: "H",
      onPress: onOpenReportsHistory,
    },
    canInv && {
      title: "Ombor",
      hint: "Kirim · chiqim · kam qoldiq",
      mark: "O",
      onPress: onOpenInventory,
    },
    canMaint && {
      title: "Ta’mir",
      hint: "Arizalar va xarajat",
      mark: "T",
      onPress: onOpenMaintenance,
    },
    canDash && {
      title: "Kunlik flash",
      hint: "OCC · ADR · RevPAR",
      mark: "F",
      onPress: onOpenFlash,
    },
    canAudit && {
      title: "Kun yopish",
      hint: "Night audit",
      mark: "N",
      onPress: onOpenNightAudit,
    },
  ].filter(Boolean) as {
    title: string;
    hint: string;
    mark: string;
    onPress: () => void;
  }[];

  const financeItems = [
    canFinance && {
      title: "City ledger",
      hint: "Kompaniya qarzlari",
      mark: "C",
      onPress: onOpenCityLedger,
    },
    canFinance && {
      title: "Xarajatlar",
      hint: "Rasxodlar ro‘yxati",
      mark: "X",
      onPress: onOpenExpenses,
    },
    canFinance && {
      title: "P&L",
      hint: "Oylik foyda hisobi",
      mark: "P",
      onPress: onOpenPnl,
    },
    canFinance && {
      title: "Kurslar (FX)",
      hint: "Valyuta · CBU sync",
      mark: "$",
      onPress: onOpenFx,
    },
    canFinance && {
      title: "Foyda ulushi",
      hint: "Hamkorlar · yechib olish",
      mark: "%",
      onPress: onOpenProfit,
    },
    canExport && {
      title: "Eksport",
      hint: "CSV · E-mehmon",
      mark: "↓",
      onPress: onOpenExports,
    },
    canAudit && {
      title: "Audit log",
      hint: "Faoliyat jurnali",
      mark: "A",
      onPress: onOpenAudit,
    },
  ].filter(Boolean) as {
    title: string;
    hint: string;
    mark: string;
    onPress: () => void;
  }[];

  const adminItems = [
    {
      title: "Profil",
      hint: "Ism · telefon · parol",
      mark: "P",
      onPress: onOpenProfile,
    },
    canHr && {
      title: "HR · xodimlar",
      hint: "Oylik · avans · payroll",
      mark: "H",
      onPress: onOpenHr,
    },
    canStaff && {
      title: "Staff / login",
      hint: "Taklif · rol · faol",
      mark: "U",
      onPress: onOpenStaff,
    },
    canSetup && {
      title: "Mehmonxona setup",
      hint: "Sozlama · xonalar · tariflar",
      mark: "⚙",
      onPress: onOpenSetup,
    },
  ].filter(Boolean) as {
    title: string;
    hint: string;
    mark: string;
    onPress: () => void;
  }[];

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Yana"
        title={me?.user.full_name || "Profil"}
        subtitle={`${me?.hotel?.name || me?.tenant.name || ""} · ${me?.role || ""}`}
        onTitlePress={onOpenProfile}
      />
      <ScrollView
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
      >
        {frontItems.length ? (
          <MenuSection title="Front desk">
            {frontItems.map((item, i) => (
              <MenuRow
                key={item.title}
                {...item}
                last={i === frontItems.length - 1}
              />
            ))}
          </MenuSection>
        ) : null}

        {opsItems.length ? (
          <MenuSection title="Operatsiya">
            {opsItems.map((item, i) => (
              <MenuRow
                key={item.title}
                {...item}
                last={i === opsItems.length - 1}
              />
            ))}
          </MenuSection>
        ) : null}

        {financeItems.length ? (
          <MenuSection title="Moliya">
            {financeItems.map((item, i) => (
              <MenuRow
                key={item.title}
                {...item}
                last={i === financeItems.length - 1}
              />
            ))}
          </MenuSection>
        ) : null}

        {adminItems.length ? (
          <MenuSection title="Boshqaruv">
            {adminItems.map((item, i) => (
              <MenuRow
                key={item.title}
                {...item}
                last={i === adminItems.length - 1}
              />
            ))}
          </MenuSection>
        ) : null}

        <Pressable
          style={({ pressed }) => [styles.logout, pressed && { opacity: 0.88 }]}
          onPress={logout}
        >
          <Text style={styles.logoutText}>Chiqish</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: {
    paddingHorizontal: space.lg,
    paddingTop: space.sm,
    paddingBottom: 120,
  },
  logout: {
    marginTop: space.xxl,
    marginBottom: space.lg,
    paddingVertical: 15,
    borderRadius: radius.md,
    alignItems: "center",
    backgroundColor: colors.night,
  },
  logoutText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 15,
    fontFamily: fontUi,
  },
});
