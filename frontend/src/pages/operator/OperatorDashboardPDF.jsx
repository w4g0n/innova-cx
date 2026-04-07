import { Document, Page, Text, View, StyleSheet, Image } from "@react-pdf/renderer";
import logo from "../../assets/nova-logo.png";
import { sanitizeText } from "./Operatorsanitize";

const styles = StyleSheet.create({
  page: {
    padding: 40,
    backgroundColor: "#e5e6ed",
    fontSize: 11,
    fontFamily: "Helvetica",
  },

  headerBox: {
    backgroundColor: "#fff",
    padding: 20,
    borderRadius: 6,
    marginBottom: 15,
  },

  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },

  logo: {
    width: 50,
    height: 50,
    marginRight: 15,
  },

  title: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#401c51",
  },

  subtitle: {
    fontSize: 12,
    color: "#401c51",
    marginTop: 4,
  },

  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
  },

  section: {
    backgroundColor: "#fff",
    padding: 15,
    borderRadius: 6,
    marginTop: 10,
  },

  sectionTitle: {
    backgroundColor: "#401c51",
    color: "#fff",
    padding: 6,
    borderRadius: 4,
    fontSize: 13,
    fontWeight: "bold",
    marginBottom: 8,
  },

  row: {
    flexDirection: "row",
    borderBottom: "1 solid #ddd",
    paddingVertical: 6,
  },

  cell: {
    flex: 1,
    fontSize: 10,
  },
});

export default function OperatorDashboardPDF({ data, range }) {
  const now = new Date();

  return (
    <Document>
      <Page size="A4" style={styles.page}>

        
        <View style={styles.headerBox}>
          <View style={styles.headerRow}>
            <Image src={logo} style={styles.logo} />
            <View>
              <Text style={styles.title}>Operator System Dashboard</Text>
              <Text style={styles.subtitle}>System Health & AI Monitoring</Text>
            </View>
          </View>

          <View style={styles.metaRow}>
            <Text>Generated: {now.toLocaleDateString()}</Text>
            <Text>Range: {range}</Text>
          </View>
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Core Services Status</Text>
          {data.coreServices.map((s) => (
            <View key={s.name} style={styles.row}>
              <Text style={styles.cell}>{sanitizeText(s.name, 100)}</Text>
              <Text style={styles.cell}>{sanitizeText(s.status, 50)}</Text>
              <Text style={styles.cell}>{sanitizeText(s.note, 300)}</Text>
            </View>
          ))}
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Error & Fallback Overview</Text>
          {Object.entries(data.errorFallbackOverview).map(([k, v]) => (
            <View key={k} style={styles.row}>
              <Text style={styles.cell}>{sanitizeText(k, 100)}</Text>
              <Text style={styles.cell}>{sanitizeText(String(v.count ?? ""), 50)}</Text>
              <Text style={styles.cell}>{sanitizeText(v.trendLabel, 100)}</Text>
            </View>
          ))}
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Integrations</Text>
          {data.integrations.map((i) => (
            <View key={i.name} style={styles.row}>
              <Text style={styles.cell}>{sanitizeText(i.name, 100)}</Text>
              <Text style={styles.cell}>{sanitizeText(i.status, 50)}</Text>
              <Text style={styles.cell}>{sanitizeText(i.note, 300)}</Text>
            </View>
          ))}
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Incident & Events</Text>
          {data.eventFeed.map((e, idx) => (
            <View key={idx} style={styles.row}>
              <Text style={styles.cell}>{sanitizeText(e.time, 50)}</Text>
              <Text style={styles.cell}>{sanitizeText(e.title, 200)}</Text>
              <Text style={styles.cell}>{sanitizeText(e.description, 500)}</Text>
            </View>
          ))}
        </View>

      </Page>
    </Document>
  );
}