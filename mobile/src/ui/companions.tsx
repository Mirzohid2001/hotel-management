import { StyleSheet, Text, TextInput, View } from "react-native";

import { FieldLabel, SegmentedTabs } from "./primitives";
import { colors, fontUi, space, ui } from "./theme";

export type CompanionDraft = {
  first_name: string;
  last_name: string;
  phone: string;
  nationality: string;
  doc_type: "passport" | "id_card";
  doc_number: string;
  issued_country: string;
  kind: "adult" | "child";
};

export function blankCompanion(kind: "adult" | "child"): CompanionDraft {
  return {
    first_name: "",
    last_name: "",
    phone: "",
    nationality: "UZ",
    doc_type: "passport",
    doc_number: "",
    issued_country: "UZ",
    kind,
  };
}

/** Extra people in the room: adults-1 + children, matching web formset slots. */
export function companionSlots(
  adults: number,
  children: number,
  prev: CompanionDraft[]
): CompanionDraft[] {
  const extraAdults = Math.max(0, adults - 1);
  const extraChildren = Math.max(0, children);
  const prevAdults = prev.filter((p) => p.kind !== "child");
  const prevChildren = prev.filter((p) => p.kind === "child");
  const next: CompanionDraft[] = [];
  for (let i = 0; i < extraAdults; i++) {
    next.push(prevAdults[i] ? { ...prevAdults[i], kind: "adult" } : blankCompanion("adult"));
  }
  for (let i = 0; i < extraChildren; i++) {
    next.push(
      prevChildren[i] ? { ...prevChildren[i], kind: "child" } : blankCompanion("child")
    );
  }
  return next;
}

export function companionPayload(rows: CompanionDraft[]) {
  return rows
    .filter((r) => r.first_name.trim() || r.doc_number.trim())
    .map((r) => ({
      first_name: r.first_name.trim(),
      last_name: r.last_name.trim(),
      phone: r.phone.trim(),
      nationality: r.nationality.trim() || "UZ",
      doc_type: r.doc_type,
      doc_number: r.doc_number.trim(),
      issued_country: r.issued_country.trim() || "UZ",
      kind: r.kind,
    }));
}

export function companionsIncomplete(rows: CompanionDraft[]): string | null {
  for (let i = 0; i < rows.length; i++) {
    if (!rows[i].first_name.trim()) {
      const who = rows[i].kind === "child" ? "bola" : "hamroh";
      return `${i + 1}-slot (${who}) ismi kerak.`;
    }
  }
  return null;
}

type EditorProps = {
  rows: CompanionDraft[];
  onChange: (rows: CompanionDraft[]) => void;
};

export function CompanionEditor({ rows, onChange }: EditorProps) {
  if (rows.length === 0) return null;

  function patch(index: number, part: Partial<CompanionDraft>) {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...part } : row)));
  }

  return (
    <View>
      <Text style={styles.title}>Xonadagi hamrohlar</Text>
      <Text style={styles.hint}>
        Asosiy mehmondan tashqari har bir kishi. Kattalar/bolalar soni shu qatorlarni ochadi.
      </Text>
      {rows.map((row, index) => (
        <View key={`${row.kind}-${index}`} style={styles.card}>
          <Text style={styles.cardTitle}>
            {row.kind === "child" ? "Bola" : "Katta"} {index + 1}
          </Text>
          <FieldLabel>Ism *</FieldLabel>
          <TextInput
            style={ui.input}
            value={row.first_name}
            onChangeText={(v) => patch(index, { first_name: v })}
            placeholder="Ism"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Familiya</FieldLabel>
          <TextInput
            style={ui.input}
            value={row.last_name}
            onChangeText={(v) => patch(index, { last_name: v })}
            placeholder="Familiya"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Telefon</FieldLabel>
          <TextInput
            style={ui.input}
            value={row.phone}
            onChangeText={(v) => patch(index, { phone: v })}
            keyboardType="phone-pad"
            placeholder="+998…"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Fuqarolik</FieldLabel>
          <TextInput
            style={ui.input}
            value={row.nationality}
            onChangeText={(v) => patch(index, { nationality: v })}
            autoCapitalize="characters"
            placeholder="UZ"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Hujjat</FieldLabel>
          <SegmentedTabs
            tabs={[
              { id: "passport", label: "Pasport" },
              { id: "id_card", label: "ID" },
            ]}
            value={row.doc_type}
            onChange={(id) => patch(index, { doc_type: id })}
          />
          <FieldLabel>Pasport / ID</FieldLabel>
          <TextInput
            style={ui.input}
            value={row.doc_number}
            onChangeText={(v) => patch(index, { doc_number: v })}
            autoCapitalize="characters"
            placeholder="AA 1234567"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Berilgan mamlakat</FieldLabel>
          <TextInput
            style={ui.input}
            value={row.issued_country}
            onChangeText={(v) => patch(index, { issued_country: v })}
            autoCapitalize="characters"
            placeholder="UZ"
            placeholderTextColor={colors.faint}
          />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  title: {
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 15,
    color: colors.ink,
    marginBottom: 4,
  },
  hint: {
    fontFamily: fontUi,
    fontSize: 12,
    lineHeight: 17,
    color: colors.muted,
    marginBottom: space.sm,
  },
  card: {
    marginTop: space.sm,
    paddingTop: space.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  cardTitle: {
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 13,
    color: colors.accentDeep,
    marginBottom: space.xs,
  },
});
