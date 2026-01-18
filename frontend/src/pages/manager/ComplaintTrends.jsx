import { useState } from "react";
import Layout from "../../components/Layout";
import "./ComplaintTrends.css";

export default function ComplaintTrends() {
  const [timeRange, setTimeRange] = useState("This Month");
  const [department, setDepartment] = useState("All Departments");
  const [priority, setPriority] = useState("All Priorities");

  const applyFilters = () => {
    alert(
      `Filters applied (demo)\nTime: ${timeRange}\nDept: ${department}\nPriority: ${priority}`
    );
  };

  return (
    <Layout role="manager">
      <div className="mgrTrends">
        <header className="mgrHeader">
          <div>
            <h1 className="mgrTitle">Complaint Trends</h1>
            <p className="mgrSubtitle">
              Track complaint volumes, resolution performance, and top categories
              over time.
            </p>
          </div>
        </header>

        <section className="filtersRow">
          <div className="filtersLeft">
            <div className="selectWrapper">
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
              >
                <option>This Month</option>
                <option>Last 3 Months</option>
                <option>Last 6 Months</option>
                <option>Last 12 Months</option>
              </select>
            </div>

            <div className="selectWrapper">
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option>All Departments</option>
                <option>Facilities Management</option>
                <option>Security</option>
                <option>Cleaning</option>
                <option>IT Support</option>
              </select>
            </div>

            <div className="selectWrapper">
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option>All Priorities</option>
                <option>Critical only</option>
                <option>High & Critical</option>
                <option>Low & Medium</option>
              </select>
            </div>
          </div>

          <button className="filterBtn" onClick={applyFilters} type="button">
            <span className="filterIcon">
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M3 4h18l-7 8v6l-4 2v-8L3 4z"
                  fill="currentColor"
                />
              </svg>
            </span>
            Apply filters
          </button>
        </section>

        <section className="kpiRow">
          <div className="kpiCard">
            <span className="kpiLabel">Complaints This Month</span>
            <span className="kpiValue">128</span>
            <span className="kpiCaption">↑ 12% vs last month</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Resolved Within SLA</span>
            <span className="kpiValue">91%</span>
            <span className="kpiCaption">Target: 90%</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Average Response Time</span>
            <span className="kpiValue">38 mins</span>
            <span className="kpiCaption">First agent response</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Average Resolve Time</span>
            <span className="kpiValue">1.6 days</span>
            <span className="kpiCaption">From creation to closure</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Top Category</span>
            <span className="kpiValue">HVAC Issues</span>
            <span className="kpiCaption">32 tickets this month</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Repeat Complaints</span>
            <span className="kpiValue">9%</span>
            <span className="kpiCaption">Same issue in 30 days</span>
          </div>
        </section>

        <section className="chartsGrid">
          <div className="card">
            <h2 className="cardTitle">Complaints Over Time</h2>
            <p className="cardSubtitle">
              Monthly volume of complaints for your department.
            </p>

            <div className="trendBars">
              <div className="trendBar" style={{ height: "55%" }}>
                <span className="trendValue">84</span>
              </div>
              <div className="trendBar" style={{ height: "70%" }}>
                <span className="trendValue">101</span>
              </div>
              <div className="trendBar" style={{ height: "82%" }}>
                <span className="trendValue">118</span>
              </div>
              <div className="trendBar" style={{ height: "100%" }}>
                <span className="trendValue">132</span>
              </div>
            </div>

            <div className="trendLabels">
              <span>Jun</span>
              <span>Jul</span>
              <span>Aug</span>
              <span>Sep</span>
            </div>
          </div>

          <aside className="card">
            <h2 className="cardTitle">Top Complaint Categories</h2>
            <p className="cardSubtitle">
              Share of complaints by type (current month).
            </p>

            <div className="categoryList">
              <div className="categoryRow">
                <span className="categoryName">HVAC / Temperature</span>
                <div className="categoryBar">
                  <div className="categoryBarFill" style={{ width: "72%" }} />
                </div>
                <span className="categoryValue">32%</span>
              </div>

              <div className="categoryRow">
                <span className="categoryName">Plumbing / Leakage</span>
                <div className="categoryBar">
                  <div className="categoryBarFill" style={{ width: "54%" }} />
                </div>
                <span className="categoryValue">24%</span>
              </div>

              <div className="categoryRow">
                <span className="categoryName">Cleaning / Housekeeping</span>
                <div className="categoryBar">
                  <div className="categoryBarFill" style={{ width: "38%" }} />
                </div>
                <span className="categoryValue">17%</span>
              </div>

              <div className="categoryRow">
                <span className="categoryName">Electrical / Lighting</span>
                <div className="categoryBar">
                  <div className="categoryBarFill" style={{ width: "28%" }} />
                </div>
                <span className="categoryValue">12%</span>
              </div>

              <div className="categoryRow">
                <span className="categoryName">Other</span>
                <div className="categoryBar">
                  <div className="categoryBarFill" style={{ width: "18%" }} />
                </div>
                <span className="categoryValue">15%</span>
              </div>
            </div>
          </aside>
        </section>

        <section className="tableWrapper">
          <h2 className="cardTitle">Monthly Trend Summary</h2>
          <p className="cardSubtitle">
            Compare volumes and SLA performance month by month.
          </p>

          <div className="trendsTableWrap">
            <table className="trendsTable">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Total Complaints</th>
                  <th>Resolved</th>
                  <th>Within SLA</th>
                  <th>Avg Response Time</th>
                  <th>Avg Resolve Time</th>
                  <th>SLA Performance</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>June</td>
                  <td>84</td>
                  <td>79</td>
                  <td>88%</td>
                  <td>45 mins</td>
                  <td>2.1 days</td>
                  <td>
                    <span className="deltaNegative">- 6%</span>
                  </td>
                </tr>
                <tr>
                  <td>July</td>
                  <td>101</td>
                  <td>95</td>
                  <td>90%</td>
                  <td>41 mins</td>
                  <td>1.9 days</td>
                  <td>
                    <span className="deltaPositive">+ 20%</span>
                  </td>
                </tr>
                <tr>
                  <td>August</td>
                  <td>118</td>
                  <td>110</td>
                  <td>92%</td>
                  <td>39 mins</td>
                  <td>1.7 days</td>
                  <td>
                    <span className="deltaPositive">+ 17%</span>
                  </td>
                </tr>
                <tr>
                  <td>September</td>
                  <td>132</td>
                  <td>124</td>
                  <td>91%</td>
                  <td>38 mins</td>
                  <td>1.6 days</td>
                  <td>
                    <span className="deltaPositive">+ 12%</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
}
