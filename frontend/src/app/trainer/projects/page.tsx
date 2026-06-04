import { redirect } from "next/navigation";

/**
 * Legacy redirect: /trainer/projects → /trainer/companies
 * Projects are now accessed through the company-centric hierarchy.
 */
export default function TrainerProjectsRedirectPage() {
  redirect("/trainer/companies");
}
