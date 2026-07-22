import { ProjectDetailSkeleton, TabBarSkeleton } from "@/components/shell/route-loading";

export default function ProjectLoading() {
  return (
    <>
      <TabBarSkeleton count={7} />
      <ProjectDetailSkeleton />
    </>
  );
}
