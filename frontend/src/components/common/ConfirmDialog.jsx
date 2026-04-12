import { createPortal } from "react-dom";
import "./ConfirmDialog.css";

/**
 * Reusable confirmation dialog.
 *
 * Props:
 *  open         – boolean, whether to show the dialog
 *  icon         – ReactNode, icon/emoji displayed at the top
 *  title        – string, dialog heading
 *  message      – string, body text
 *  confirmLabel – string (default "Confirm")
 *  cancelLabel  – string (default "Cancel")
 *  onConfirm    – function called when user confirms
 *  onCancel     – function called when user cancels / clicks backdrop
 *  variant      – "danger" | "warning" | "info" | "success"
 */
export default function ConfirmDialog({
  open,
  icon,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  variant = "danger",
}) {
  if (!open) return null;

  const dialog = (
    <div className="cd__overlay" onMouseDown={onCancel}>
      <div className="cd__box" onMouseDown={(e) => e.stopPropagation()}>
        {icon && (
          <div className={`cd__iconWrap cd__iconWrap--${variant}`}>{icon}</div>
        )}
        <div className="cd__title">{title}</div>
        {message && <div className="cd__message">{message}</div>}
        <div className="cd__actions">
          <button className="cd__btnCancel" type="button" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={`cd__btnConfirm cd__btnConfirm--${variant}`}
            type="button"
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(dialog, document.body) : dialog;
}
