import AsyncStorage from "@react-native-async-storage/async-storage";
import { RU } from "./i18nCatalog";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "uz" | "ru";

const KEY = "pms.lang";

const STR = {
  uz: {
    tabBoard: "Doska",
    tabToday: "Bugun",
    tabCalendar: "Taqvim",
    tabHk: "Toza",
    tabMore: "Yana",
    loginEyebrow: "Kirish",
    loginTitle: "Hisobingizga kiring",
    loginHint: "Web bilan bir xil login",
    loginUser: "Login",
    loginPass: "Parol",
    loginBtn: "Kirish",
    logout: "Chiqish",
    profile: "Profil",
    language: "Til",
    langUz: "O‘zbekcha",
    langRu: "Ruscha",
    allHotels: "Barcha filiallar",
    hotelPick: "Qaysi filial?",
    newBranch: "Yangi filial",
    widget: "Onlayn bron",
    deleteBooking: "O‘chirish",
    deleteGuest: "Mehmonni o‘chirish",
    deleteAccount: "Hisobni o‘chirish",
    logo: "Logotip",
    saved: "Saqlandi",
  },
  ru: {
    tabBoard: "Доска",
    tabToday: "Сегодня",
    tabCalendar: "Календарь",
    tabHk: "Уборка",
    tabMore: "Ещё",
    loginEyebrow: "Вход",
    loginTitle: "Войдите в аккаунт",
    loginHint: "Тот же логин, что и на сайте",
    loginUser: "Логин",
    loginPass: "Пароль",
    loginBtn: "Войти",
    logout: "Выйти",
    profile: "Профиль",
    language: "Язык",
    langUz: "Узбекский",
    langRu: "Русский",
    allHotels: "Все филиалы",
    hotelPick: "Какой филиал?",
    newBranch: "Новый филиал",
    widget: "Онлайн-бронь",
    deleteBooking: "Удалить",
    deleteGuest: "Удалить гостя",
    deleteAccount: "Удалить аккаунт",
    logo: "Логотип",
    saved: "Сохранено",
  },
} as const;

type Key = keyof (typeof STR)["uz"];

type Ctx = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: Key) => string;
  tr: (phrase: string) => string;
};

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("uz");

  useEffect(() => {
    AsyncStorage.getItem(KEY).then((v) => {
      if (v === "ru" || v === "uz") setLangState(v);
    });
  }, []);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    AsyncStorage.setItem(KEY, next).catch(() => undefined);
  }, []);

  const t = useCallback((key: Key) => STR[lang][key], [lang]);
  const tr = useCallback(
    (phrase: string) => (lang === "ru" ? RU[phrase] ?? phrase : phrase),
    [lang]
  );
  const value = useMemo(
    () => ({ lang, setLang, t, tr }),
    [lang, setLang, t, tr]
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
