import { useParams } from "react-router-dom";
import Layout from "../../components/Layout";

export default function ComplaintDetails() {
  const { id } = useParams();

  return (
    <Layout role="employee">
      <h2>Complaint Details</h2>
      <p>Complaint ID: {id}</p>
      <p>Paste Complaint Details UI here.</p>
    </Layout>
  );
}
