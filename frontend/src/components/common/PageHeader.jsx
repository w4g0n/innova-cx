import "./PageHeader.css";

export default function PageHeader({ title, subtitle, actions = null }) {
  return (
    <header className="pageHeader">
      <span className="pageHeader__backdrop" aria-hidden="true" />
      <div className="pageHeader__content">
        <div className="pageHeader__text">
          <span className="pageHeader__eyebrow" aria-hidden="true" />
          <h1 className="pageHeader__title">{title}</h1>
          {subtitle ? <p className="pageHeader__subtitle">{subtitle}</p> : null}
        </div>

        {actions ? <div className="pageHeader__actions">{actions}</div> : null}
      </div>
    </header>
  );
}
