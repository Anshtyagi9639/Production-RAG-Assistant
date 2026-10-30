"use client"

import { useQuery } from "@tanstack/react-query"
import { FileText, Search, Upload } from "lucide-react"
import { useRef } from "react"

import { useWorkspace } from "@/components/app/workspace-context"
import { DocumentsTable } from "@/components/documents/documents-table"
import { SearchPanel } from "@/components/documents/search-panel"
import { UploadDropzone, type UploadDropzoneHandle } from "@/components/documents/upload-dropzone"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { statsApi } from "@/lib/api/endpoints"
import { queryKeys } from "@/lib/query-keys"

export default function KnowledgeBasePage() {
  const { workspace } = useWorkspace()
  const isOwner = workspace.role === "owner"
  const dropzone = useRef<UploadDropzoneHandle>(null)
  const stats = useQuery({
    queryKey: queryKeys.stats(workspace.id),
    queryFn: () => statsApi.get(workspace.id),
  })
  const hasDocuments = (stats.data?.documents.total ?? 0) > 0

  return (
    <>
      <PageHeader
        title="Knowledge Base"
        description="Documents in this workspace. Each upload is extracted, split into passages and indexed, so the Assistant and Agent can cite it."
        actions={
          isOwner && (
            <Button onClick={() => dropzone.current?.openPicker()}>
              <Upload aria-hidden />
              Upload documents
            </Button>
          )
        }
      />
      {/* Outside the tabs so the header's Upload button works from either tab. */}
      {isOwner && (
        <div className="mb-6">
          <UploadDropzone ref={dropzone} workspaceId={workspace.id} compact={hasDocuments} />
        </div>
      )}
      <Tabs defaultValue="documents" className="gap-5">
        <TabsList>
          <TabsTrigger value="documents">
            <FileText aria-hidden />
            Documents
          </TabsTrigger>
          <TabsTrigger value="search">
            <Search aria-hidden />
            Semantic search
          </TabsTrigger>
        </TabsList>
        <TabsContent value="documents">
          <DocumentsTable workspaceId={workspace.id} canDelete={isOwner} />
        </TabsContent>
        <TabsContent value="search">
          <SearchPanel workspaceId={workspace.id} />
        </TabsContent>
      </Tabs>
    </>
  )
}
