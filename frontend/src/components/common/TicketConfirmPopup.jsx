import AudioReplyPlayer from "./AudioReplyPlayer";
import "./TicketConfirmPopup.css";

/**
 * TicketConfirmPopup — modal overlay confirming that a complaint/inquiry
 * has been received. Plays a TTS audio confirmation via AudioReplyPlayer.
 *
 * Props:
 *   open       - whether to show the popup
 *   ticketId   - ticket code (e.g. "CX-12345") or null
 *   isInquiry  - true for inquiry, false for complaint
 *   replyText  - confirmation message text
 *   enableAudio - play audio confirmation when true
 *   onClose    - callback when user dismisses the popup
 */
export default function TicketConfirmPopup({
  open,
  ticketId,
  isInquiry = false,
  replyText = "",
  enableAudio = false,
  onClose,
}) {
  if (!open) return null;

  const displayText =
    replyText ||
    (isInquiry
      ? "Your inquiry has been received. Our team will respond shortly."
      : `Your complaint has been successfully logged. Ticket ID: ${ticketId}. Our team will review your concern.`);

  return (
    <div className="tcp__overlay" onMouseDown={onClose}>
      <div className="tcp__box" onMouseDown={(e) => e.stopPropagation()}>
        {/* Success icon — green checkmark */}
        <div className="tcp__iconWrap">
          <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
            <circle cx="26" cy="26" r="26" fill="rgba(46, 204, 113, 0.12)" />
            <path
              d="M15 26.5l8 8 14-16"
              stroke="#2ecc71"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <div className="tcp__title">
          {isInquiry ? "Inquiry Received" : "Complaint Logged"}
        </div>

        {ticketId && !isInquiry && (
          <div className="tcp__ticketId">
            Ticket ID: <strong>{ticketId}</strong>
          </div>
        )}

        <p className="tcp__message">{displayText}</p>

        {enableAudio && (
          <AudioReplyPlayer
            ticketId={ticketId}
            isInquiry={isInquiry}
            replyText={displayText}
          />
        )}

        <button className="tcp__btnClose" type="button" onClick={onClose}>
          Continue
        </button>
      </div>
    </div>
  );
}