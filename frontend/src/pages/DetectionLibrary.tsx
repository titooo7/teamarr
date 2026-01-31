import { useState, useRef } from "react"
import { toast } from "sonner"
import {
  Plus,
  Trash2,
  Pencil,
  Loader2,
  Download,
  Upload,
  ToggleLeft,
  ToggleRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  useDetectionKeywords,
  useDetectionCategories,
  useCreateDetectionKeyword,
  useUpdateDetectionKeyword,
  useDeleteDetectionKeyword,
  useBulkImportDetectionKeywords,
  exportDetectionKeywords,
  type CategoryType,
  type DetectionKeyword,
  type DetectionKeywordCreate,
} from "@/api/detectionKeywords"

const CATEGORY_ORDER: CategoryType[] = [
  "combat_sports",
  "league_hints",
  "sport_hints",
  "placeholders",
  "card_segments",
  "exclusions",
  "separators",
]

export function DetectionLibrary() {
  const [activeCategory, setActiveCategory] = useState<CategoryType>("combat_sports")
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [editingKeyword, setEditingKeyword] = useState<DetectionKeyword | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<DetectionKeyword | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const categoriesQuery = useDetectionCategories()
  const keywordsQuery = useDetectionKeywords(activeCategory)
  const createMutation = useCreateDetectionKeyword()
  const updateMutation = useUpdateDetectionKeyword()
  const deleteMutation = useDeleteDetectionKeyword()
  const importMutation = useBulkImportDetectionKeywords()

  const categories = categoriesQuery.data?.categories || []
  const keywords = keywordsQuery.data?.keywords || []
  const activeInfo = categories.find((c) => c.id === activeCategory)

  // Form state for add/edit
  const [formData, setFormData] = useState<{
    keyword: string
    is_regex: boolean
    target_value: string
    enabled: boolean
    priority: number
    description: string
  }>({
    keyword: "",
    is_regex: false,
    target_value: "",
    enabled: true,
    priority: 0,
    description: "",
  })

  const resetForm = () => {
    setFormData({
      keyword: "",
      is_regex: false,
      target_value: "",
      enabled: true,
      priority: 0,
      description: "",
    })
  }

  const openAddDialog = () => {
    resetForm()
    setShowAddDialog(true)
  }

  const openEditDialog = (keyword: DetectionKeyword) => {
    setFormData({
      keyword: keyword.keyword,
      is_regex: keyword.is_regex,
      target_value: keyword.target_value || "",
      enabled: keyword.enabled,
      priority: keyword.priority,
      description: keyword.description || "",
    })
    setEditingKeyword(keyword)
  }

  const handleCreate = async () => {
    try {
      const data: DetectionKeywordCreate = {
        category: activeCategory,
        keyword: formData.keyword.trim(),
        is_regex: formData.is_regex,
        target_value: formData.target_value.trim() || null,
        enabled: formData.enabled,
        priority: formData.priority,
        description: formData.description.trim() || null,
      }
      await createMutation.mutateAsync(data)
      toast.success(`Created keyword "${data.keyword}"`)
      setShowAddDialog(false)
      resetForm()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create keyword")
    }
  }

  const handleUpdate = async () => {
    if (!editingKeyword) return
    try {
      await updateMutation.mutateAsync({
        id: editingKeyword.id,
        data: {
          keyword: formData.keyword.trim(),
          is_regex: formData.is_regex,
          target_value: formData.target_value.trim() || null,
          enabled: formData.enabled,
          priority: formData.priority,
          description: formData.description.trim() || null,
          clear_target_value: !formData.target_value.trim(),
          clear_description: !formData.description.trim(),
        },
      })
      toast.success(`Updated keyword "${formData.keyword}"`)
      setEditingKeyword(null)
      resetForm()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update keyword")
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await deleteMutation.mutateAsync(deleteConfirm.id)
      toast.success(`Deleted keyword "${deleteConfirm.keyword}"`)
      setDeleteConfirm(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete keyword")
    }
  }

  const handleToggleEnabled = async (keyword: DetectionKeyword) => {
    try {
      await updateMutation.mutateAsync({
        id: keyword.id,
        data: { enabled: !keyword.enabled },
      })
      toast.success(`${keyword.enabled ? "Disabled" : "Enabled"} keyword "${keyword.keyword}"`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to toggle keyword")
    }
  }

  const handleExport = async () => {
    try {
      const data = await exportDetectionKeywords(activeCategory)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `detection-keywords-${activeCategory}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`Exported ${data.count} keywords`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to export keywords")
    }
  }

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setIsImporting(true)
    try {
      const text = await file.text()
      const imported = JSON.parse(text)

      // Handle both array format and export format
      const keywords = Array.isArray(imported) ? imported : imported.keywords
      if (!Array.isArray(keywords)) {
        throw new Error("Invalid format: expected keywords array")
      }

      const result = await importMutation.mutateAsync({ keywords })
      toast.success(`Imported: ${result.created} created, ${result.updated} updated`)
      if (result.failed > 0) {
        toast.warning(`${result.failed} keywords failed to import`)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to import keywords")
    } finally {
      setIsImporting(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    }
  }

  if (categoriesQuery.error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Detection Library</h1>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">
              Error loading categories: {categoriesQuery.error.message}
            </p>
            <Button className="mt-4" onClick={() => categoriesQuery.refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Detection Library</h1>
          <p className="text-sm text-muted-foreground">
            Manage detection patterns for stream classification
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-1" />
            Export
          </Button>
          <Button variant="outline" size="sm" onClick={handleImportClick} disabled={isImporting}>
            {isImporting ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 mr-1" />
            )}
            Import
          </Button>
          <Button size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4 mr-1" />
            Add Keyword
          </Button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          className="hidden"
          onChange={handleImportFile}
        />
      </div>

      {/* Category Tabs */}
      <div className="flex gap-1 border-b border-border">
        {CATEGORY_ORDER.map((catId) => {
          const cat = categories.find((c) => c.id === catId)
          if (!cat) return null
          return (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3 py-1.5 text-sm font-medium rounded-t transition-colors ${
                activeCategory === cat.id
                  ? "bg-card text-foreground border border-border border-b-card -mb-px"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
              }`}
            >
              {cat.name}
            </button>
          )
        })}
      </div>

      {/* Category Description */}
      {activeInfo && (
        <div className="text-sm text-muted-foreground bg-secondary/30 px-3 py-2 rounded">
          {activeInfo.description}
          {activeInfo.has_target && activeInfo.target_description && (
            <span className="ml-2 text-primary">
              Target: {activeInfo.target_description}
            </span>
          )}
        </div>
      )}

      {/* Keywords Table */}
      <div className="border border-border rounded-lg overflow-hidden">
        {keywordsQuery.isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : keywords.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No keywords in this category. Add one to get started.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Keyword/Pattern</TableHead>
                {activeInfo?.has_target && <TableHead className="w-[20%]">Target</TableHead>}
                <TableHead className="w-[80px]">Type</TableHead>
                <TableHead className="w-[80px]">Priority</TableHead>
                <TableHead className="w-[80px]">Status</TableHead>
                <TableHead className="w-[120px] text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keywords.map((kw) => (
                <TableRow key={kw.id} className={!kw.enabled ? "opacity-50" : ""}>
                  <TableCell>
                    <div className="flex flex-col">
                      <code className="text-sm font-mono bg-muted px-1 rounded">
                        {kw.keyword}
                      </code>
                      {kw.description && (
                        <span className="text-xs text-muted-foreground mt-0.5">
                          {kw.description}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  {activeInfo?.has_target && (
                    <TableCell>
                      {kw.target_value ? (
                        <code className="text-sm font-mono">{kw.target_value}</code>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  )}
                  <TableCell>
                    <Badge variant={kw.is_regex ? "info" : "secondary"}>
                      {kw.is_regex ? "regex" : "text"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">{kw.priority}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={kw.enabled ? "success" : "secondary"}>
                      {kw.enabled ? "On" : "Off"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleToggleEnabled(kw)}
                        title={kw.enabled ? "Disable" : "Enable"}
                      >
                        {kw.enabled ? (
                          <ToggleRight className="h-4 w-4 text-green-500" />
                        ) : (
                          <ToggleLeft className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => openEditDialog(kw)}
                        title="Edit"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setDeleteConfirm(kw)}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Add/Edit Dialog */}
      <Dialog
        open={showAddDialog || editingKeyword !== null}
        onOpenChange={(open) => {
          if (!open) {
            setShowAddDialog(false)
            setEditingKeyword(null)
            resetForm()
          }
        }}
      >
        <DialogContent
          onClose={() => {
            setShowAddDialog(false)
            setEditingKeyword(null)
            resetForm()
          }}
        >
          <DialogHeader>
            <DialogTitle>{editingKeyword ? "Edit Keyword" : "Add Keyword"}</DialogTitle>
            <DialogDescription>
              {activeInfo?.description}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Keyword/Pattern</label>
              <Input
                value={formData.keyword}
                onChange={(e) => setFormData((f) => ({ ...f, keyword: e.target.value }))}
                placeholder={formData.is_regex ? "regex pattern" : "keyword text"}
              />
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.is_regex}
                  onCheckedChange={(checked) => setFormData((f) => ({ ...f, is_regex: checked }))}
                />
                <label className="text-sm">Regular expression</label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.enabled}
                  onCheckedChange={(checked) => setFormData((f) => ({ ...f, enabled: checked }))}
                />
                <label className="text-sm">Enabled</label>
              </div>
            </div>

            {activeInfo?.has_target && (
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Target Value
                  {activeInfo.target_description && (
                    <span className="text-muted-foreground font-normal ml-1">
                      ({activeInfo.target_description})
                    </span>
                  )}
                </label>
                <Input
                  value={formData.target_value}
                  onChange={(e) => setFormData((f) => ({ ...f, target_value: e.target.value }))}
                  placeholder="e.g., nfl, Hockey, main_card"
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">Priority</label>
              <Input
                type="number"
                value={formData.priority}
                onChange={(e) =>
                  setFormData((f) => ({ ...f, priority: parseInt(e.target.value) || 0 }))
                }
                placeholder="0"
              />
              <p className="text-xs text-muted-foreground">
                Higher priority patterns are checked first
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData((f) => ({ ...f, description: e.target.value }))}
                placeholder="Optional description"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowAddDialog(false)
                setEditingKeyword(null)
                resetForm()
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={editingKeyword ? handleUpdate : handleCreate}
              disabled={
                !formData.keyword.trim() ||
                createMutation.isPending ||
                updateMutation.isPending
              }
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {editingKeyword ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={deleteConfirm !== null}
        onOpenChange={(open) => !open && setDeleteConfirm(null)}
      >
        <DialogContent onClose={() => setDeleteConfirm(null)}>
          <DialogHeader>
            <DialogTitle>Delete Keyword</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{deleteConfirm?.keyword}"? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
