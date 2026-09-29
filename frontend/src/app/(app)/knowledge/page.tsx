"use client"

import { useWorkspace } from "@/components/app/workspace-context"
import { DocumentsTable } from "@/components/documents/documents-table"
import { SearchPanel } from "@/components/documents/search-panel"
import { UploadDropzone } from "@/components/documents/upload-dropzone"
import { PageHeader } from "@/components/page-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function KnowledgeBasePage() {
  const { workspace } = useWorkspace()
  const isOwner = workspace.role === "owner"

  return (
    <>
      <PageHeader
        title="Knowledge Base"
        description="Documents in this workspace. Each upload is extracted, split into passages and indexed for search."
      />
      <Tabs defaultValue="documents" className="space-y-4">
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
        </TabsList>
        <TabsContent value="documents" className="space-y-6">
          {isOwner && <UploadDropzone workspaceId={workspace.id} />}
          <DocumentsTable workspaceId={workspace.id} canDelete={isOwner} />
        </TabsContent>
        <TabsContent value="search">
          <SearchPanel workspaceId={workspace.id} />
        </TabsContent>
      </Tabs>
    </>
  )
}
