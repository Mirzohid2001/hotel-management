import { useState } from "react";
import { StatusBar } from "expo-status-bar";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { BoardTile } from "./src/api/types";
import { AuthProvider, useAuth } from "./src/auth/AuthContext";
import { BoardScreen } from "./src/screens/BoardScreen";
import { BookingScreen } from "./src/screens/BookingScreen";
import { CalendarScreen } from "./src/screens/CalendarScreen";
import { CashShiftScreen } from "./src/screens/CashShiftScreen";
import { CityLedgerScreen } from "./src/screens/CityLedgerScreen";
import { CompaniesScreen } from "./src/screens/CompaniesScreen";
import { FinanceScreen } from "./src/screens/FinanceScreen";
import { FlashScreen } from "./src/screens/FlashScreen";
import { GroupsScreen } from "./src/screens/GroupsScreen";
import { GuestsScreen } from "./src/screens/GuestsScreen";
import { HousekeepingScreen } from "./src/screens/HousekeepingScreen";
import { HrScreen } from "./src/screens/HrScreen";
import { InquiriesScreen } from "./src/screens/InquiriesScreen";
import { InventoryScreen } from "./src/screens/InventoryScreen";
import { LoginScreen } from "./src/screens/LoginScreen";
import { MaintenanceScreen } from "./src/screens/MaintenanceScreen";
import { MoreScreen } from "./src/screens/MoreScreen";
import { NightAuditScreen } from "./src/screens/NightAuditScreen";
import { ReferrersScreen } from "./src/screens/ReferrersScreen";
import { ReservationDetailScreen } from "./src/screens/ReservationDetailScreen";
import { TodayScreen } from "./src/screens/TodayScreen";
import { WalkInScreen } from "./src/screens/WalkInScreen";
import { colors, fontUi } from "./src/ui/theme";

type WalkInRoom = BoardTile["room"];
type Tab = "board" | "today" | "calendar" | "housekeeping" | "more";
type Overlay =
  | null
  | "booking"
  | "cash"
  | "guests"
  | "inquiries"
  | "flash"
  | "maintenance"
  | "companies"
  | "city_ledger"
  | "groups"
  | "night_audit"
  | "expenses"
  | "pnl"
  | "inventory"
  | "referrers"
  | "hr";

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "board", icon: "▦", label: "Doska" },
  { id: "today", icon: "◎", label: "Bugun" },
  { id: "calendar", icon: "☰", label: "Taqvim" },
  { id: "housekeeping", icon: "◇", label: "Toza" },
  { id: "more", icon: "···", label: "Yana" },
];

function Root() {
  const { ready, token } = useAuth();
  const [tab, setTab] = useState<Tab>("board");
  const [reservationId, setReservationId] = useState<number | null>(null);
  const [walkInRoom, setWalkInRoom] = useState<WalkInRoom | null>(null);
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [boardReload, setBoardReload] = useState(0);

  if (!ready) {
    return (
      <View style={styles.boot}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (!token) {
    return <LoginScreen />;
  }

  if (overlay === "cash") {
    return <CashShiftScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "booking") {
    return (
      <BookingScreen
        onBack={() => setOverlay(null)}
        onCreated={(id) => {
          setOverlay(null);
          setBoardReload((n) => n + 1);
          setReservationId(id);
        }}
      />
    );
  }
  if (overlay === "guests") {
    return (
      <GuestsScreen
        onBack={() => setOverlay(null)}
        onOpenReservation={(id) => {
          setOverlay(null);
          setReservationId(id);
        }}
      />
    );
  }
  if (overlay === "inquiries") {
    return (
      <InquiriesScreen
        onBack={() => setOverlay(null)}
        onOpenReservation={(id) => {
          setOverlay(null);
          setReservationId(id);
        }}
      />
    );
  }
  if (overlay === "flash") {
    return <FlashScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "maintenance") {
    return (
      <MaintenanceScreen
        onBack={() => {
          setOverlay(null);
          setBoardReload((n) => n + 1);
        }}
      />
    );
  }
  if (overlay === "companies") {
    return <CompaniesScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "city_ledger") {
    return <CityLedgerScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "groups") {
    return (
      <GroupsScreen
        onBack={() => setOverlay(null)}
        onOpenReservation={(id) => {
          setOverlay(null);
          setReservationId(id);
        }}
      />
    );
  }
  if (overlay === "night_audit") {
    return <NightAuditScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "expenses") {
    return <FinanceScreen onBack={() => setOverlay(null)} mode="expenses" />;
  }
  if (overlay === "pnl") {
    return <FinanceScreen onBack={() => setOverlay(null)} mode="pnl" />;
  }
  if (overlay === "inventory") {
    return <InventoryScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "referrers") {
    return <ReferrersScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "hr") {
    return <HrScreen onBack={() => setOverlay(null)} />;
  }

  if (walkInRoom) {
    return (
      <WalkInScreen
        room={walkInRoom}
        onBack={() => setWalkInRoom(null)}
        onCreated={(id) => {
          setWalkInRoom(null);
          setBoardReload((n) => n + 1);
          setReservationId(id);
        }}
      />
    );
  }

  if (reservationId != null) {
    return (
      <ReservationDetailScreen
        reservationId={reservationId}
        onBack={() => setReservationId(null)}
        onChanged={() => setBoardReload((n) => n + 1)}
      />
    );
  }

  return (
    <View style={styles.shell}>
      <View style={styles.main}>
        {tab === "board" ? (
          <BoardScreen
            onOpenReservation={setReservationId}
            onWalkIn={setWalkInRoom}
            onNewBooking={() => setOverlay("booking")}
            onCashShift={() => setOverlay("cash")}
            onOpenGuests={() => setOverlay("guests")}
            onOpenInquiries={() => setOverlay("inquiries")}
            onOpenFlash={() => setOverlay("flash")}
            onOpenMaintenance={() => setOverlay("maintenance")}
            onOpenCalendar={() => setTab("calendar")}
            onOpenHousekeeping={() => setTab("housekeeping")}
            reloadToken={boardReload}
            onHotelChanged={() => setBoardReload((n) => n + 1)}
          />
        ) : tab === "today" ? (
          <TodayScreen
            onOpenReservation={setReservationId}
            reloadToken={boardReload}
            onHotelChanged={() => setBoardReload((n) => n + 1)}
          />
        ) : tab === "calendar" ? (
          <CalendarScreen onOpenReservation={setReservationId} />
        ) : tab === "housekeeping" ? (
          <HousekeepingScreen onChanged={() => setBoardReload((n) => n + 1)} />
        ) : (
          <MoreScreen
            onOpenGuests={() => setOverlay("guests")}
            onOpenInquiries={() => setOverlay("inquiries")}
            onOpenCash={() => setOverlay("cash")}
            onNewBooking={() => setOverlay("booking")}
            onOpenFlash={() => setOverlay("flash")}
            onOpenMaintenance={() => setOverlay("maintenance")}
            onOpenCompanies={() => setOverlay("companies")}
            onOpenCityLedger={() => setOverlay("city_ledger")}
            onOpenGroups={() => setOverlay("groups")}
            onOpenNightAudit={() => setOverlay("night_audit")}
            onOpenExpenses={() => setOverlay("expenses")}
            onOpenPnl={() => setOverlay("pnl")}
            onOpenInventory={() => setOverlay("inventory")}
            onOpenReferrers={() => setOverlay("referrers")}
            onOpenHr={() => setOverlay("hr")}
          />
        )}
      </View>
      <View style={styles.tabBar}>
        {TABS.map(({ id, icon, label }) => {
          const on = tab === id;
          return (
            <Pressable key={id} style={styles.tab} onPress={() => setTab(id)}>
              <Text style={[styles.tabIcon, on && styles.tabIconOn]}>{icon}</Text>
              <Text style={[styles.tabText, on && styles.tabTextOn]}>{label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <StatusBar style="light" />
      <Root />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.paper,
  },
  shell: { flex: 1, backgroundColor: colors.paper },
  main: { flex: 1 },
  tabBar: {
    flexDirection: "row",
    backgroundColor: colors.night,
    paddingBottom: 22,
    paddingTop: 8,
    paddingHorizontal: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "rgba(255,255,255,0.1)",
  },
  tab: { flex: 1, alignItems: "center", paddingVertical: 6, gap: 2 },
  tabIcon: {
    fontSize: 16,
    color: colors.nightFogDim,
    fontWeight: "600",
    height: 22,
  },
  tabIconOn: { color: colors.accentSoft },
  tabText: {
    color: colors.nightFogDim,
    fontWeight: "600",
    fontSize: 10,
    fontFamily: fontUi,
  },
  tabTextOn: { color: colors.white, fontWeight: "700" },
});
