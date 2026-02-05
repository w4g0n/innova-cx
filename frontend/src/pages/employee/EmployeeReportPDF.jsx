import { Document, Page, Text, View, StyleSheet, Image } from "@react-pdf/renderer";
import logo from "../../assets/nova-logo.png";

const styles = StyleSheet.create({
  page: {
    padding: 40,
    backgroundColor: "#e5e6ed",
    fontSize: 11,
    fontFamily: "Helvetica",
    color: "#000",
  },
  metadataSection: {
    backgroundColor: "#fff",
    padding: 20,
    borderRadius: 6,
    marginBottom: 15,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },
  logo: {
    width: 60,
    height: 60,
    marginRight: 20,
  },
  titleSection: {
    flexDirection: "column",
    justifyContent: "center",
  },
  reportTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#401c51",
  },
  employeeName: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#401c51",
    marginTop: 4,
  },
  subtitle: {
    marginTop: 4,
    color: "#401c51",
    fontSize: 12,
  },
  metadataRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 10,
  },
  metadataItem: {
    fontSize: 11,
  },
  metadataLabel: {
    fontWeight: "bold",
  },
  section: {
    backgroundColor: "#fff",
    padding: 15,
    borderRadius: 6,
    marginTop: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "bold",
    marginBottom: 8,
    color: "#fff",
    backgroundColor: "#401c51",
    padding: 6,
    borderRadius: 4,
  },
  kpiRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 10,
  },
  kpiBox: {
    width: "23%",
    padding: 12,
    backgroundColor: "#fff",
    color: "#000"
  },
  kpiLabel: {
    fontSize: 9,
    color: "#000",
  },
  kpiValue: {
    fontSize: 16,
    fontWeight: "bold",
    marginTop: 4,
    color: "#000",
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: "#fff",
    paddingVertical: 6,
    paddingHorizontal: 4,
    marginBottom: 4,
    color: "#000",
    fontWeight: "bold",
    borderBottom: "1 solid #ccc",
  },
  tableRow: {
    flexDirection: "row",
    borderBottom: "1 solid #ccc",
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  tableCell: {
    flex: 1,
    fontSize: 10,
  },
  note: {
    marginTop: 6,
    fontSize: 10,
    lineHeight: 1.4,
  },
});

export default function EmployeeReportPDF({ report, employeeName, employeeId, downloadDate }) {
  return (
    <Document>
      <Page size="A4" style={styles.page}>
        
        <View style={styles.metadataSection}>
          <View style={styles.header}>
            <Image src={logo} style={styles.logo} />
            <View style={styles.titleSection}>
              <Text style={styles.reportTitle}>Monthly Performance Report</Text>
              <Text style={styles.subtitle}>{report.month}</Text>
            </View>
          </View>

          <View style={styles.metadataRow}>
            <Text style={styles.metadataItem}>
              <Text style={styles.metadataLabel}>Employee ID: </Text>{employeeId}
            </Text>
            <Text style={styles.metadataItem}>
              <Text style={styles.metadataLabel}>Name: </Text>{employeeName}
            </Text>
          </View>
          <View style={styles.metadataRow}>
            <Text style={styles.metadataItem}>
              <Text style={styles.metadataLabel}>Date: </Text>{downloadDate.toLocaleDateString()}
            </Text>
            <Text style={styles.metadataItem}>
              <Text style={styles.metadataLabel}>Time: </Text>{downloadDate.toLocaleTimeString()}
            </Text>
          </View>
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Key Performance Indicators</Text>
          <View style={styles.kpiRow}>
            <View style={styles.kpiBox}>
              <Text style={styles.kpiLabel}>Overall Rating</Text>
              <Text style={styles.kpiValue}>{report.kpis.rating}</Text>
            </View>
            <View style={styles.kpiBox}>
              <Text style={styles.kpiLabel}>Resolved</Text>
              <Text style={styles.kpiValue}>{report.kpis.resolved}</Text>
            </View>
            <View style={styles.kpiBox}>
              <Text style={styles.kpiLabel}>SLA Compliance</Text>
              <Text style={styles.kpiValue}>{report.kpis.sla}</Text>
            </View>
            <View style={styles.kpiBox}>
              <Text style={styles.kpiLabel}>Avg Response</Text>
              <Text style={styles.kpiValue}>{report.kpis.avgResponse}</Text>
            </View>
          </View>
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Summary Breakdown</Text>
          {report.summary.map((s) => (
            <View key={s.label} style={styles.tableRow}>
              <Text style={styles.tableCell}>{s.label}</Text>
              <Text style={styles.tableCell}>{s.value}</Text>
            </View>
          ))}
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Weekly Activity</Text>
          <View style={styles.tableHeader}>
            <Text style={styles.tableCell}>Week</Text>
            <Text style={styles.tableCell}>Assigned</Text>
            <Text style={styles.tableCell}>Resolved</Text>
            <Text style={styles.tableCell}>SLA</Text>
            <Text style={styles.tableCell}>Avg Response</Text>
          </View>
          {report.weekly.map((w) => (
            <View key={w.week} style={styles.tableRow}>
              <Text style={styles.tableCell}>{w.week}</Text>
              <Text style={styles.tableCell}>{w.assigned}</Text>
              <Text style={styles.tableCell}>{w.resolved}</Text>
              <Text style={styles.tableCell}>{w.sla}</Text>
              <Text style={styles.tableCell}>{w.avg}</Text>
            </View>
          ))}
        </View>

        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Insights & Notes</Text>
          {report.notes.map((n, i) => (
            <Text key={i} style={styles.note}>• {n}</Text>
          ))}
        </View>
      </Page>
    </Document>
  );
}