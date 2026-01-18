import React, { useState, useMemo } from "react";
import Layout from "../../components/Layout";
import "./ViewAllComplaint.css";

export default function TicketDetails() {
  return (
    <Layout role="employee">
        {/* MAIN CONTENT */}
        <main className="main">

        {/* HEADER */}
        <div className="details-header">
            <div className="header-left">
            <button className="back-btn">← Back</button>
            <h1 className="ticket-title">Ticket ID: CX-1122</h1>

            <div className="status-row">
                <span className="header-pill critical-pill">Critical</span>
                <span className="header-pill status-pill">Submitted</span>
            </div>
            </div>

            <div className="header-actions">
            <button className="btn-outline" onClick={openRescore}>Rescore</button>
            <button className="btn-outline" onClick={openReroute}>Reroute</button>
            <button className="btn-primary" onClick={openResolve}>Resolve</button>
            </div>
        </div>

        {/* SUMMARY INFO */}
        <section className="card-section">
            <h2 className="section-title">Summary</h2>

            <div className="summary-grid">
            <div><span className="label">Issue Date:</span> 18/11/2025</div>
            <div><span className="label">Mean Time To Respond:</span> 6 Hours</div>
            <div><span className="label">Mean Time To Resolve:</span> 30 Minutes</div>
            <div><span className="label">Submitted By:</span> John Smith</div>
            <div><span className="label">Contact:</span> +971 50 123 4567</div>
            <div><span className="label">Location:</span> Building A, Floor 3</div>
            </div>
        </section>

        <section className="details-grid">

            {/* Complaint Details */}
            <div className="card-section">
            <h2 className="section-title">Complaint Details</h2>

            <div className="subject">Air conditioning not working</div>

            <p className="description">
                The AC unit in the main office stopped cooling around 11 AM. Room temperature rose significantly, affecting employees. Issue may be related to compressor or electrical supply.
            </p>

            <div className="attachments">
                <div className="attachment-thumb">IMG 1</div>
                <div className="attachment-thumb">IMG 2</div>
            </div>
            </div>

            {/* Steps Taken */}
            <div className="card-section">
            <h2 className="section-title">Steps Taken</h2>

            <div className="step">
                <div className="step-title">Step 1</div>
                <div className="step-text">
                Technician assigned: Ahmed Khan<br />
                Time: 18/11/2025 – 10:15 AM<br />
                Notes: Technician informed and en route.
                </div>
            </div>

            <div className="step">
                <div className="step-title">Step 2</div>
                <div className="step-text">
                Technician arrived on-site<br />
                Time: 18/11/2025 – 10:45 AM<br />
                Notes: Compressor overheating.
                </div>
            </div>

            </div>

        </section>

        </main>

    </Layout>
  );
}
