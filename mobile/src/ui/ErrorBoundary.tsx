import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, fontUi, radius, space } from "./theme";

type Props = { children: React.ReactNode };

type State = { error: Error | null };

/** Catches render crashes so we don't get a silent white screen. */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("[ErrorBoundary]", error);
  }

  render() {
    if (this.state.error) {
      return (
        <View style={styles.wrap}>
          <Text style={styles.eyebrow}>XATO</Text>
          <Text style={styles.title}>Ilova ishlamay qoldi</Text>
          <Text style={styles.msg}>{this.state.error.message}</Text>
          <Pressable
            style={styles.btn}
            onPress={() => this.setState({ error: null })}
          >
            <Text style={styles.btnText}>Qayta urinish</Text>
          </Pressable>
        </View>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: colors.night,
    padding: space.xl,
    justifyContent: "center",
  },
  eyebrow: {
    color: colors.accentSoft,
    fontFamily: fontUi,
    fontWeight: "700",
    letterSpacing: 1.2,
    fontSize: 11,
    marginBottom: 8,
  },
  title: {
    color: colors.white,
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 22,
    marginBottom: space.md,
  },
  msg: {
    color: colors.nightFog,
    fontFamily: fontUi,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: space.xl,
  },
  btn: {
    alignSelf: "flex-start",
    backgroundColor: colors.accent,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: radius.md,
  },
  btnText: {
    color: colors.white,
    fontFamily: fontUi,
    fontWeight: "700",
  },
});
