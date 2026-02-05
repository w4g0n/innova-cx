import "./PageHeader.css";

export default function PageHeader({ title, subtitle, actions = null }) {
  return (
    <header className="pageHeader">
      <div className="pageHeader__text">
        <h1 className="pageHeader__title">{title}</h1>
        {subtitle ? <p className="pageHeader__subtitle">{subtitle}</p> : null}
      </div>

      {actions ? <div className="pageHeader__actions">{actions}</div> : null}
    </header>
  );
}