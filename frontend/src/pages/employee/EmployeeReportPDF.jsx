import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Image,
} from "@react-pdf/renderer";
import logo from "../../assets/nova-logo.png";

// ── Brand palette ─────────────────────────────────────────────────────────────
const B = {
  purple:      "#5924b4",
  purpleDark:  "#3b0f6e",
  purpleDeep:  "#1e0a3c",
  purpleMid:   "#7c3aed",
  purpleLight: "#c4b5fd",
  purpleTint:  "#f3e8ff",
  purpleFaint: "#faf8ff",
  white:       "#ffffff",
  bg:          "#f4f1fb",
  border:      "#e8e0f5",
  text:        "#111111",
  textMid:     "#4b4060",
  muted:       "#7a6f95",
  mutedLight:  "#b0a8c8",
  green:       "#059669",
  amber:       "#d97706",
  red:         "#dc2626",
};

const S = StyleSheet.create({

  // ── Page ────────────────────────────────────────────────────────────────────
  page: {
    backgroundColor: B.bg,
    paddingHorizontal: 0,
    paddingTop: 0,
    paddingBottom: 48,
    fontFamily: "Helvetica",
    fontSize: 9,
    color: B.text,
  },

  // ── Hero ────────────────────────────────────────────────────────────────────
  hero: {
    backgroundColor: B.purpleDeep,
    paddingTop: 26,
    paddingBottom: 22,
    paddingHorizontal: 34,
  },
  heroAccent: {
    position: "absolute",
    top: 0, left: 0, right: 0,
    height: 4,
    backgroundColor: B.purpleMid,
  },
  heroRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  heroLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  heroLogo: {
    width: 44,
    height: 44,
  },
  heroTitles: {
    flexDirection: "column",
  },
  heroEyebrow: {
    fontSize: 7,
    fontFamily: "Helvetica-Bold",
    color: B.purpleLight,
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 4,
  },
  heroTitle: {
    fontSize: 20,
    fontFamily: "Helvetica-Bold",
    color: B.white,
    letterSpacing: -0.3,
  },
  heroMonth: {
    fontSize: 11,
    color: "rgba(196,181,253,0.8)",
    marginTop: 4,
    fontFamily: "Helvetica-Oblique",
  },
  heroPills: {
    flexDirection: "column",
    alignItems: "flex-end",
    gap: 5,
  },
  heroPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderRadius: 6,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  heroPillLabel: {
    fontSize: 7,
    fontFamily: "Helvetica-Bold",
    color: "rgba(196,181,253,0.65)",
    textTransform: "uppercase",
    letterSpacing: 0.7,
  },
  heroPillVal: {
    fontSize: 8,
    fontFamily: "Helvetica-Bold",
    color: B.white,
  },

  // ── Hero bottom ledge ────────────────────────────────────────────────────────
  heroLedge: {
    height: 14,
    backgroundColor: B.purpleDeep,
    marginBottom: 22,
  },

  // ── Body ─────────────────────────────────────────────────────────────────────
  body: {
    paddingHorizontal: 28,
  },

  sectionLabel: {
    fontSize: 7,
    fontFamily: "Helvetica-Bold",
    textTransform: "uppercase",
    letterSpacing: 1,
    color: B.muted,
    marginBottom: 9,
    marginTop: 2,
  },

  // ── KPI strip ────────────────────────────────────────────────────────────────
  kpiStrip: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 16,
  },
  kpiCard: {
    flex: 1,
    backgroundColor: B.white,
    borderRadius: 10,
    paddingVertical: 13,
    paddingHorizontal: 13,
    borderWidth: 1,
    borderColor: B.border,
    position: "relative",
    overflow: "hidden",
  },
  kpiTopBar: {
    position: "absolute",
    top: 0, left: 0, right: 0,
    height: 3,
  },
  kpiLabel: {
    fontSize: 7,
    fontFamily: "Helvetica-Bold",
    textTransform: "uppercase",
    letterSpacing: 0.6,
    color: B.muted,
    marginBottom: 7,
    marginTop: 5,
  },
  kpiValLg: {
    fontSize: 22,
    fontFamily: "Helvetica-Bold",
    letterSpacing: -0.5,
    color: B.text,
  },
  kpiValMd: {
    fontSize: 14,
    fontFamily: "Helvetica-Bold",
    letterSpacing: -0.3,
  },
  ratingExcellent: { color: B.green },
  ratingGood:      { color: B.green },
  ratingNeeds:     { color: B.amber },
  ratingPoor:      { color: B.red   },

  // ── Two-column layout ─────────────────────────────────────────────────────────
  twoCol: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 12,
  },
  colWide:   { flex: 1.45 },
  colNarrow: { flex: 1 },

  // ── Card shell ───────────────────────────────────────────────────────────────
  card: {
    backgroundColor: B.white,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: B.border,
    overflow: "hidden",
  },
  cardHead: {
    backgroundColor: B.purpleDark,
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    paddingVertical: 9,
    paddingHorizontal: 14,
  },
  cardHeadDot: {
    width: 7, height: 7,
    borderRadius: 4,
    backgroundColor: B.purpleLight,
  },
  cardHeadText: {
    fontSize: 10,
    fontFamily: "Helvetica-Bold",
    color: B.white,
    letterSpacing: 0.2,
  },
  cardBody: {
    paddingHorizontal: 14,
    paddingVertical: 12,
  },

  // ── Summary rows ─────────────────────────────────────────────────────────────
  sumRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 7,
    borderBottomWidth: 1,
    borderBottomColor: B.border,
  },
  sumRowAlt: {
    backgroundColor: B.purpleFaint,
    marginHorizontal: -14,
    paddingHorizontal: 16,
  },
  sumRowLast:  { borderBottomWidth: 0 },
  sumLabel:    { fontSize: 9, color: B.muted },
  sumVal:      { fontSize: 9, fontFamily: "Helvetica-Bold", color: B.text },

  // ── Employee profile card ─────────────────────────────────────────────────────
  empAvatar: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: B.purple,
    alignItems: "center", justifyContent: "center",
    marginBottom: 8, alignSelf: "center",
  },
  empInitials: {
    fontSize: 17, fontFamily: "Helvetica-Bold", color: B.white,
  },
  empName: {
    fontSize: 11, fontFamily: "Helvetica-Bold", color: B.purpleDeep,
    textAlign: "center", marginBottom: 2,
  },
  empId: {
    fontSize: 8, color: B.muted, fontFamily: "Helvetica-Bold",
    textAlign: "center", marginBottom: 12,
  },
  statRow: {
    flexDirection: "row",
    gap: 8,
  },
  statChip: {
    flex: 1,
    backgroundColor: B.bg,
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: B.border,
    alignItems: "center",
  },
  statChipLabel: {
    fontSize: 7, fontFamily: "Helvetica-Bold",
    textTransform: "uppercase", letterSpacing: 0.5,
    color: B.muted, marginBottom: 4, textAlign: "center",
  },
  statChipVal: {
    fontSize: 14, fontFamily: "Helvetica-Bold",
    color: B.purple, textAlign: "center",
  },

  // ── Weekly table ──────────────────────────────────────────────────────────────
  tableCard: {
    backgroundColor: B.white,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: B.border,
    overflow: "hidden",
    marginBottom: 12,
  },
  tHead: {
    flexDirection: "row",
    backgroundColor: B.bg,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: B.border,
  },
  tHeadCell: {
    flex: 1,
    fontSize: 7,
    fontFamily: "Helvetica-Bold",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    color: B.muted,
    textAlign: "center",
  },
  tHeadCellFirst: { textAlign: "left" },
  tRow: {
    flexDirection: "row",
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: B.border,
  },
  tRowAlt:  { backgroundColor: B.purpleFaint },
  tRowLast: { borderBottomWidth: 0 },
  tCell: { flex: 1, fontSize: 9, color: B.text, textAlign: "center" },
  tCellFirst: {
    textAlign: "left",
    fontFamily: "Helvetica-Bold",
    color: B.purple,
  },

  // ── Notes ─────────────────────────────────────────────────────────────────────
  notesCard: {
    backgroundColor: B.white,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: B.border,
    overflow: "hidden",
    marginBottom: 12,
  },
  noteRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 9,
    paddingVertical: 7,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: B.border,
  },
  noteRowLast: { borderBottomWidth: 0 },
  noteDot: {
    width: 6, height: 6, borderRadius: 3,
    backgroundColor: B.purpleLight,
    marginTop: 2, flexShrink: 0,
  },
  noteText: {
    flex: 1, fontSize: 9, color: B.textMid, lineHeight: 1.55,
  },

  // ── Footer ────────────────────────────────────────────────────────────────────
  footer: {
    position: "absolute",
    bottom: 16, left: 28, right: 28,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: B.border,
  },
  footerL: { fontSize: 7, color: B.mutedLight },
  footerC: { fontSize: 7, color: B.purple, fontFamily: "Helvetica-Bold", letterSpacing: 0.3 },
  footerR: { fontSize: 7, color: B.mutedLight },
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function initials(name = "") {
  return name.split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase() || "").join("");
}

function ratingStyle(rating = "") {
  // Numeric score support (e.g. "4.7 / 5" or "4.7")
  const numMatch = rating.match(/[\d.]+/);
  if (numMatch) {
    const score = parseFloat(numMatch[0]);
    if (score >= 4.0) return S.ratingExcellent; // green
    if (score >= 2.5) return S.ratingNeeds;     // amber
    return S.ratingPoor;                         // red
  }
  // Text-based ratings
  if (rating === "Excellent") return S.ratingExcellent; // green
  if (rating === "Good")      return S.ratingGood;      // green
  if (rating === "Needs Improvement") return S.ratingNeeds; // amber
  return S.ratingPoor; // red
}

const KPI_COLORS = [B.purple, B.purple, B.purple, B.purple];

// ── PDF Component ─────────────────────────────────────────────────────────────
export default function EmployeeReportPDF({ report, employeeName, employeeId, downloadDate }) {
  const { month, kpis, summary, weekly, notes } = report;

  const dateStr = downloadDate
    ? new Intl.DateTimeFormat("en-US", { dateStyle: "long" }).format(downloadDate)
    : "—";
  const timeStr = downloadDate
    ? new Intl.DateTimeFormat("en-US", { timeStyle: "short" }).format(downloadDate)
    : "—";

  const kpiItems = [
    { label: "Overall Rating",   value: kpis.rating,           isRating: true },
    { label: "Resolved Tickets", value: String(kpis.resolved)                 },
    { label: "SLA Compliance",   value: kpis.sla                              },
    { label: "Avg Response",     value: kpis.avgResponse                      },
  ];

  return (
    <Document>
      <Page size="A4" style={S.page}>

        {/* HERO */}
        <View style={S.hero}>
          <View style={S.heroAccent} />
          <View style={S.heroRow}>
            <View style={S.heroLeft}>
              <Image src={logo} style={S.heroLogo} />
              <View style={S.heroTitles}>
                <Text style={S.heroEyebrow}>Performance Report</Text>
                <Text style={S.heroTitle}>Monthly Review</Text>
                <Text style={S.heroMonth}>{month}</Text>
              </View>
            </View>
            <View style={S.heroPills}>
              {[
                { label: "Employee", val: employeeName },
                { label: "ID",       val: employeeId   },
                { label: "Date",     val: dateStr       },
                { label: "Time",     val: timeStr       },
              ].map((p) => (
                <View key={p.label} style={S.heroPill}>
                  <Text style={S.heroPillLabel}>{p.label}</Text>
                  <Text style={S.heroPillVal}>{p.val}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* Hero ledge */}
        <View style={S.heroLedge} />

        <View style={S.body}>

          {/* KPI STRIP */}
          <Text style={S.sectionLabel}>Key Performance Indicators</Text>
          <View style={S.kpiStrip}>
            {kpiItems.map((k, i) => (
              <View key={k.label} style={S.kpiCard}>
                <View style={[S.kpiTopBar, { backgroundColor: KPI_COLORS[i] }]} />
                <Text style={S.kpiLabel}>{k.label}</Text>
                <Text
                  style={
                    k.isRating
                      ? [S.kpiValMd, ratingStyle(k.value)]
                      : S.kpiValLg
                  }
                >
                  {k.value}
                </Text>
              </View>
            ))}
          </View>

          {/* TWO-COL: Summary + Employee profile */}
          <View style={S.twoCol}>

            <View style={S.colWide}>
              <View style={S.card}>
                <View style={S.cardHead}>
                  <View style={S.cardHeadDot} />
                  <Text style={S.cardHeadText}>Summary Breakdown</Text>
                </View>
                <View style={S.cardBody}>
                  {summary.map((row, i) => (
                    <View
                      key={row.label}
                      style={[
                        S.sumRow,
                        i % 2 === 1 && S.sumRowAlt,
                        i === summary.length - 1 && S.sumRowLast,
                      ]}
                    >
                      <Text style={S.sumLabel}>{row.label}</Text>
                      <Text style={S.sumVal}>{row.value}</Text>
                    </View>
                  ))}
                </View>
              </View>
            </View>

            <View style={S.colNarrow}>
              <View style={S.card}>
                <View style={S.cardHead}>
                  <View style={S.cardHeadDot} />
                  <Text style={S.cardHeadText}>Employee Profile</Text>
                </View>
                <View style={S.cardBody}>
                  <View style={S.empAvatar}>
                    <Text style={S.empInitials}>{initials(employeeName)}</Text>
                  </View>
                  <Text style={S.empName}>{employeeName}</Text>
                  <Text style={S.empId}>{employeeId}</Text>
                  <View style={S.statRow}>
                    <View style={S.statChip}>
                      <Text style={S.statChipLabel}>Resolved</Text>
                      <Text style={S.statChipVal}>{kpis.resolved}</Text>
                    </View>
                    <View style={S.statChip}>
                      <Text style={S.statChipLabel}>SLA</Text>
                      <Text style={S.statChipVal}>{kpis.sla}</Text>
                    </View>
                  </View>
                </View>
              </View>
            </View>

          </View>

          {/* WEEKLY TABLE */}
          <View style={S.tableCard}>
            <View style={S.cardHead}>
              <View style={S.cardHeadDot} />
              <Text style={S.cardHeadText}>Weekly Activity</Text>
            </View>
            <View style={S.tHead}>
              <Text style={[S.tHeadCell, S.tHeadCellFirst]}>Week</Text>
              <Text style={S.tHeadCell}>Assigned</Text>
              <Text style={S.tHeadCell}>Resolved</Text>
              <Text style={S.tHeadCell}>SLA</Text>
              <Text style={S.tHeadCell}>Avg Response</Text>
            </View>
            {weekly.map((row, i) => (
              <View
                key={row.week}
                style={[
                  S.tRow,
                  i % 2 === 1 && S.tRowAlt,
                  i === weekly.length - 1 && S.tRowLast,
                ]}
              >
                <Text style={[S.tCell, S.tCellFirst]}>{row.week}</Text>
                <Text style={S.tCell}>{row.assigned}</Text>
                <Text style={S.tCell}>{row.resolved}</Text>
                <Text style={S.tCell}>{row.sla}</Text>
                <Text style={S.tCell}>{row.avg}</Text>
              </View>
            ))}
          </View>

          {/* NOTES */}
          <View style={S.notesCard}>
            <View style={S.cardHead}>
              <View style={S.cardHeadDot} />
              <Text style={S.cardHeadText}>Insights & Notes</Text>
            </View>
            {notes.map((note, i) => (
              <View
                key={i}
                style={[S.noteRow, i === notes.length - 1 && S.noteRowLast]}
              >
                <View style={S.noteDot} />
                <Text style={S.noteText}>{note}</Text>
              </View>
            ))}
          </View>

        </View>

        {/* FOOTER */}
        <View style={S.footer} fixed>
          <Text style={S.footerL}>Confidential · {employeeName} ({employeeId})</Text>
          <Text style={S.footerC}>CX Platform · Performance Reports</Text>
          <Text
            style={S.footerR}
            render={({ pageNumber, totalPages }) => `Page ${pageNumber} of ${totalPages}`}
          />
        </View>

      </Page>
    </Document>
  );
}
