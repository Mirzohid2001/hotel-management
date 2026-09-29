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
import { FxScreen } from "./src/screens/FxScreen";
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
import { SetupScreen } from "./src/screens/SetupScreen";
import { StaffScreen } from "./src/screens/StaffScreen";
import { AuditLogScreen } from "./src/screens/AuditLogScreen";
import { ExportsScreen } from "./src/screens/ExportsScreen";
import { NotificationsScreen } from "./src/screens/NotificationsScreen";
import { TodayScreen } from "./src/screens/TodayScreen";
import { WalkInScreen } from "./src/screens/WalkInScreen";
import { MinibarQuickScreen } from "./src/screens/MinibarQuickScreen";
import { ReservationsListScreen } from "./src/screens/ReservationsListScreen";
import { DashboardScreen } from "./src/screens/DashboardScreen";
import { ServicesScreen } from "./src/screens/ServicesScreen";
import { ReportsHistoryScreen } from "./src/screens/ReportsHistoryScreen";
import { ProfileScreen } from "./src/screens/ProfileScreen";
import { colors, fontUi } from "./src/ui/theme";
import { ErrorBoundary } from "./src/ui/ErrorBoundary";

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
  | "profit"
  | "fx"
  | "inventory"
  | "referrers"
  | "hr"
  | "setup"
  | "staff"
  | "audit"
  | "exports"
  | "notifications"
  | "minibar"
  | "bronlar"
  | "dashboard"
  | "services"
  | "reports_history"
  | "profile";

type BookingDraft = {
  roomId?: number | null;
  checkIn?: string | null;
};

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "board", icon: "▦", label: "Doska" },
  { id: "today", icon: "◎", label: "Bugun" },
  { id: "calendar", icon: "▤", label: "Taqvim" },
  { id: "housekeeping", icon: "◇", label: "Toza" },
  { id: "more", icon: "⋯", label: "Yana" },
];

function Root() {
  const { ready, token } = useAuth();
  const [tab, setTab] = useState<Tab>("board");
  const [reservationId, setReservationId] = useState<number | null>(null);
  const [walkInRoom, setWalkInRoom] = useState<WalkInRoom | null>(null);
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [bookingDraft, setBookingDraft] = useState<BookingDraft>({});
  const [boardReload, setBoardReload] = useState(0);
  const [flashDate, setFlashDate] = useState<string | undefined>(undefined);
  const [pnlPeriod, setPnlPeriod] = useState<{ year?: number; month?: number }>({});

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
        onBack={() => {
          setOverlay(null);
          setBookingDraft({});
        }}
        initialRoomId={bookingDraft.roomId}
        initialCheckIn={bookingDraft.checkIn}
        onCreated={(id) => {
          setOverlay(null);
          setBookingDraft({});
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
    return (
      <FlashScreen
        onBack={() => {
          setOverlay(null);
          setFlashDate(undefined);
        }}
        initialDate={flashDate}
      />
    );
  }
  if (overlay === "minibar") {
    return <MinibarQuickScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "bronlar") {
    return (
      <ReservationsListScreen
        onBack={() => setOverlay(null)}
        onOpenReservation={(id) => {
          setOverlay(null);
          setReservationId(id);
        }}
      />
    );
  }
  if (overlay === "dashboard") {
    return (
      <DashboardScreen
        onBack={() => setOverlay(null)}
        onOpenFlash={() => {
          setFlashDate(undefined);
          setOverlay("flash");
        }}
        onOpenBoard={() => {
          setOverlay(null);
          setTab("board");
        }}
        onOpenHousekeeping={() => {
          setOverlay(null);
          setTab("housekeeping");
        }}
        onOpenInquiries={() => setOverlay("inquiries")}
        onOpenCityLedger={() => setOverlay("city_ledger")}
      />
    );
  }
  if (overlay === "services") {
    return <ServicesScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "reports_history") {
    return (
      <ReportsHistoryScreen
        onBack={() => setOverlay(null)}
        onOpenFlash={(date) => {
          setFlashDate(date);
          setOverlay("flash");
        }}
        onOpenPnl={(year, month) => {
          setPnlPeriod({ year, month });
          setOverlay("pnl");
        }}
      />
    );
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
    return (
      <CompaniesScreen
        onBack={() => setOverlay(null)}
        onOpenReservation={(id) => {
          setOverlay(null);
          setReservationId(id);
        }}
      />
    );
  }
  if (overlay === "profile") {
    return <ProfileScreen onBack={() => setOverlay(null)} />;
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
    return (
      <FinanceScreen
        onBack={() => {
          setOverlay(null);
          setPnlPeriod({});
        }}
        mode="pnl"
        year={pnlPeriod.year}
        month={pnlPeriod.month}
      />
    );
  }
  if (overlay === "profit") {
    return <FinanceScreen onBack={() => setOverlay(null)} mode="profit" />;
  }
  if (overlay === "fx") {
    return <FxScreen onBack={() => setOverlay(null)} />;
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
  if (overlay === "setup") {
    return <SetupScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "staff") {
    return <StaffScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "audit") {
    return <AuditLogScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "exports") {
    return <ExportsScreen onBack={() => setOverlay(null)} />;
  }
  if (overlay === "notifications") {
    return (
      <NotificationsScreen
        onBack={() => setOverlay(null)}
        onOpen={(target, id) => {
          if (target === "reservation" && id) {
            setOverlay(null);
            setReservationId(id);
            return;
          }
          if (target === "maintenance" || target === "inventory") {
            setOverlay(target);
          }
        }}
      />
    );
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
            onNewBooking={() => {
              setBookingDraft({});
              setOverlay("booking");
            }}
            onCashShift={() => setOverlay("cash")}
            onOpenGuests={() => setOverlay("guests")}
            onOpenInquiries={() => setOverlay("inquiries")}
            onOpenFlash={() => setOverlay("flash")}
            onOpenDashboard={() => setOverlay("dashboard")}
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
          <CalendarScreen
            onOpenReservation={setReservationId}
            onQuickBook={(roomId, date) => {
              setBookingDraft({ roomId, checkIn: date });
              setOverlay("booking");
            }}
          />
        ) : tab === "housekeeping" ? (
          <HousekeepingScreen onChanged={() => setBoardReload((n) => n + 1)} />
        ) : (
          <MoreScreen
            onOpenGuests={() => setOverlay("guests")}
            onOpenInquiries={() => setOverlay("inquiries")}
            onOpenCash={() => setOverlay("cash")}
            onNewBooking={() => {
              setBookingDraft({});
              setOverlay("booking");
            }}
            onOpenFlash={() => setOverlay("flash")}
            onOpenMaintenance={() => setOverlay("maintenance")}
            onOpenCompanies={() => setOverlay("companies")}
            onOpenCityLedger={() => setOverlay("city_ledger")}
            onOpenGroups={() => setOverlay("groups")}
            onOpenNightAudit={() => setOverlay("night_audit")}
            onOpenExpenses={() => setOverlay("expenses")}
            onOpenPnl={() => setOverlay("pnl")}
            onOpenProfit={() => setOverlay("profit")}
            onOpenFx={() => setOverlay("fx")}
            onOpenInventory={() => setOverlay("inventory")}
            onOpenReferrers={() => setOverlay("referrers")}
            onOpenHr={() => setOverlay("hr")}
            onOpenSetup={() => setOverlay("setup")}
            onOpenStaff={() => setOverlay("staff")}
            onOpenAudit={() => setOverlay("audit")}
            onOpenExports={() => setOverlay("exports")}
            onOpenNotifications={() => setOverlay("notifications")}
            onOpenMinibar={() => setOverlay("minibar")}
            onOpenBronlar={() => setOverlay("bronlar")}
            onOpenDashboard={() => setOverlay("dashboard")}
            onOpenServices={() => setOverlay("services")}
            onOpenReportsHistory={() => setOverlay("reports_history")}
            onOpenProfile={() => setOverlay("profile")}
          />
        )}
      </View>
      <View style={styles.tabBar}>
        {TABS.map(({ id, icon, label }) => {
          const on = tab === id;
          return (
            <Pressable
              key={id}
              style={({ pressed }) => [
                styles.tab,
                on && styles.tabOn,
                pressed && { opacity: 0.85 },
              ]}
              onPress={() => setTab(id)}
            >
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
    <ErrorBoundary>
      <AuthProvider>
        <StatusBar style="light" />
        <Root />
      </AuthProvider>
    </ErrorBoundary>
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
    paddingBottom: 20,
    paddingTop: 10,
    paddingHorizontal: 8,
    gap: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "rgba(255,255,255,0.08)",
  },
  tab: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
    borderRadius: 12,
    gap: 3,
  },
  tabOn: {
    backgroundColor: "rgba(196,92,38,0.22)",
  },
  tabIcon: {
    fontSize: 15,
    color: colors.nightFogDim,
    fontWeight: "600",
    height: 20,
  },
  tabIconOn: { color: colors.accentSoft },
  tabText: {
    color: colors.nightFogDim,
    fontWeight: "600",
    fontSize: 10,
    fontFamily: fontUi,
    letterSpacing: 0.2,
  },
  tabTextOn: { color: colors.white, fontWeight: "700" },
});
