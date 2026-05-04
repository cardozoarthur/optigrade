import React from "react";
import TeacherPortalClient from "./TeacherPortalClient";

export default async function TeacherPortal({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <TeacherPortalClient token={token} />;
}

