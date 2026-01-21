import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import { useNavigate } from "react-router-dom";
import "./CustomerLanding.css";

export default function CustomerLanding() {
  const navigate = useNavigate();

  return (
    <Layout role="customer">
      <div className="custLanding">
        <PageHeader
          title="Dubai CommerCity Support"
          subtitle="Chat with Nova for quick help, or submit a complaint/inquiry via form."
        />

        <section className="custHero">
          <div className="custHero__left">
            <h2 className="custHero__headline">
              Fast help, clear tracking, and smarter resolutions.
            </h2>
            <p className="custHero__text">
              Use the chatbot for instant assistance. If you prefer, you can submit a form
              anytime—text or audio—and we’ll route it to the right team.
            </p>

            <div className="custHero__actions">
              <button
                type="button"
                className="primaryPillBtn"
                onClick={() => navigate("/customer/chatbot")}
              >
                Start Chatbot
              </button>

              <button
                type="button"
                className="custSecondaryBtn"
                onClick={() => navigate("/customer/fill-form")}
              >
                Fill a Form
              </button>
            </div>

            <div className="custMetaRow">
              <div className="custMeta">
                <div className="custMeta__label">Availability</div>
                <div className="custMeta__value">24/7 Chatbot</div>
              </div>
              <div className="custMeta">
                <div className="custMeta__label">Forms</div>
                <div className="custMeta__value">Text or Audio</div>
              </div>
              <div className="custMeta">
                <div className="custMeta__label">Tracking</div>
                <div className="custMeta__value">History & Ticket Details</div>
              </div>
            </div>
          </div>

          <div className="custHero__right">
            <div className="custPromoCard">
              <div className="custPromoCard__top">
                <span className="custBadge">Nova AI Assistant</span>
              </div>

              <div className="custChatMock">
                <div className="custBubble custBubble--bot">
                  Hi! I’m Nova. How can I help you today?
                </div>
                <div className="custBubble custBubble--user">
                  I want to raise a complaint.
                </div>
                <div className="custBubble custBubble--bot">
                  Sure — you can submit it via chat or fill a form. Which do you prefer?
                </div>
              </div>

              <div className="custOptionRow">
                <button
                  type="button"
                  className="custOption"
                  onClick={() => navigate("/customer/chatbot")}
                >
                  Raise a Complaint
                </button>
                <button
                  type="button"
                  className="custOption"
                  onClick={() => navigate("/customer/chatbot")}
                >
                  Ask an Inquiry
                </button>
                <button
                  type="button"
                  className="custOption"
                  onClick={() => navigate("/customer/fill-form")}
                >
                  Fill a Form
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="custGrid">
          <article className="custInfoCard">
            <h3 className="custInfoTitle">1) Start with Chat</h3>
            <p className="custInfoText">
              Nova greets you first and offers quick options. You can type or use the mic
              (we’ll add the mic flow in the chatbot screen next).
            </p>
          </article>

          <article className="custInfoCard">
            <h3 className="custInfoTitle">2) Submit a Form Anytime</h3>
            <p className="custInfoText">
              Prefer not to chat? Use “Fill a Form” from the sidebar. Your name and email
              can be auto-filled from login.
            </p>
          </article>

          <article className="custInfoCard">
            <h3 className="custInfoTitle">3) Track Everything</h3>
            <p className="custInfoText">
              View your inquiry/complaint history and open any ticket to see details, status,
              and updates.
            </p>
          </article>
        </section>

        <section className="custHelpBar">
          <div className="custHelpBar__left">
            <div className="custHelpTitle">Need something specific?</div>
            <div className="custHelpText">
              Start the chatbot for guided help, or go straight to the form.
            </div>
          </div>

          <div className="custHelpBar__right">
            <button
              type="button"
              className="primaryPillBtn"
              onClick={() => navigate("/customer/chatbot")}
            >
              Open Chatbot
            </button>
            <button
              type="button"
              className="custSecondaryBtn"
              onClick={() => navigate("/customer/fill-form")}
            >
              Open Form
            </button>
          </div>
        </section>
      </div>
    </Layout>
  );
}
