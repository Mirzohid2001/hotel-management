import { Alert, Platform } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";

async function shareBase64File(
  base64: string,
  filename: string,
  mimeType: string,
  uti?: string
): Promise<void> {
  try {
    const dir = FileSystem.cacheDirectory || FileSystem.documentDirectory;
    if (!dir) {
      Alert.alert("Fayl", "Fayl tizimi mavjud emas");
      return;
    }
    const path = `${dir}${filename.replace(/[^\w.-]+/g, "_")}`;
    await FileSystem.writeAsStringAsync(path, base64, {
      encoding: FileSystem.EncodingType.Base64,
    });
    const can = await Sharing.isAvailableAsync();
    if (!can) {
      Alert.alert(
        "Fayl",
        Platform.OS === "web" ? "Webda ulashish yo‘q" : "Ulashish mavjud emas"
      );
      return;
    }
    await Sharing.shareAsync(path, {
      mimeType,
      dialogTitle: filename,
      UTI: uti,
    });
  } catch (e) {
    Alert.alert(
      "Fayl",
      e instanceof Error ? e.message : "Faylni ulashib bo‘lmadi"
    );
  }
}

/** Share a base64 PDF via the system sheet. */
export async function sharePdfBase64(
  base64: string,
  filename = "invoice.pdf"
): Promise<void> {
  await shareBase64File(base64, filename, "application/pdf", "com.adobe.pdf");
}

/** Share a base64 CSV via the system sheet. */
export async function shareCsvBase64(
  base64: string,
  filename = "export.csv"
): Promise<void> {
  await shareBase64File(base64, filename, "text/csv", "public.comma-separated-values-text");
}
