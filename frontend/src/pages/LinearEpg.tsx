import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Plus, Trash2, RefreshCw, Loader2, Globe, Edit, Copy } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface Monitor {
  id: number
  tvg_id: string
  display_name: string | null
  xmltv_url: string
  xmltv_channel_id: string | null
  include_sports: string[]
  enabled: boolean
}

type FormMode = "create" | "edit" | null

export function LinearEpg() {
  const queryClient = useQueryClient()
  const [formMode, setFormMode] = useState<FormMode>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [formData, setFormData] = useState({
    tvg_id: "",
    display_name: "",
    xmltv_url: "",
    xmltv_channel_id: "",
  })

  // Fetch monitors
  const { data: monitors, isLoading } = useQuery<Monitor[]>({
    queryKey: ["linear-monitors"],
    queryFn: async () => {
      const resp = await fetch("/api/v1/linear-epg/monitors")
      if (!resp.ok) throw new Error("Failed to fetch monitors")
      return resp.json()
    }
  })

  // Create monitor mutation
  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      const resp = await fetch("/api/v1/linear-epg/monitors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      })
      if (!resp.ok) throw new Error("Failed to create monitor")
      return resp.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["linear-monitors"] })
      toast.success("Monitor added successfully")
      resetForm()
    }
  })

  // Update monitor mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: any }) => {
      const resp = await fetch(`/api/v1/linear-epg/monitors/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      })
      if (!resp.ok) throw new Error("Failed to update monitor")
      return resp.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["linear-monitors"] })
      toast.success("Monitor updated successfully")
      resetForm()
    }
  })

  // Delete monitor mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const resp = await fetch(`/api/v1/linear-epg/monitors/${id}`, { method: "DELETE" })
      if (!resp.ok) throw new Error("Failed to delete monitor")
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["linear-monitors"] })
      toast.success("Monitor deleted")
    }
  })

  // Refresh cache mutation
  const refreshMutation = useMutation({
    mutationFn: async () => {
      const resp = await fetch("/api/v1/linear-epg/refresh", { method: "POST" })
      if (!resp.ok) throw new Error("Failed to trigger refresh")
    },
    onSuccess: () => {
      toast.success("Linear EPG refresh triggered")
    }
  })

  const resetForm = () => {
    setFormMode(null)
    setEditingId(null)
    setFormData({ tvg_id: "", display_name: "", xmltv_url: "", xmltv_channel_id: "" })
  }

  const handleEdit = (monitor: Monitor) => {
    setFormMode("edit")
    setEditingId(monitor.id)
    setFormData({
      tvg_id: monitor.tvg_id,
      display_name: monitor.display_name || "",
      xmltv_url: monitor.xmltv_url,
      xmltv_channel_id: monitor.xmltv_channel_id || "",
    })
  }

  const handleClone = (monitor: Monitor) => {
    setFormMode("create")
    setEditingId(null)
    setFormData({
      tvg_id: "", // Clear tvg_id for clone - user needs to set new one
      display_name: monitor.display_name || "",
      xmltv_url: monitor.xmltv_url,
      xmltv_channel_id: monitor.xmltv_channel_id || "",
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.tvg_id || !formData.xmltv_url) {
      toast.error("TVG ID and XMLTV URL are required")
      return
    }

    if (formMode === "edit" && editingId !== null) {
      updateMutation.mutate({ id: editingId, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const getFormTitle = () => {
    if (formMode === "edit") return "Edit Linear Monitor"
    return "Add Linear Monitor"
  }

  const getFormDescription = () => {
    if (formMode === "edit") return "Update linear channel configuration"
    return "Configure a linear channel to track"
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Linear EPG Discovery</h1>
          <p className="text-muted-foreground">
            Manage linear channels to monitor for sports events via external EPG.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            {refreshMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh Cache
          </Button>
          <Button onClick={() => setFormMode("create")}>
            <Plus className="mr-2 h-4 w-4" />
            Add Monitor
          </Button>
        </div>
      </div>

      {formMode && (
        <Card className="bg-muted/30">
          <CardHeader>
            <CardTitle>{getFormTitle()}</CardTitle>
            <CardDescription>{getFormDescription()}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="tvg_id">TVG ID (M3U Match)</Label>
                  <Input
                    id="tvg_id"
                    value={formData.tvg_id}
                    onChange={e => setFormData({...formData, tvg_id: e.target.value})}
                    placeholder="e.g. mligadecampeones1.es"
                    disabled={formMode === "edit"} // Cannot change tvg_id when editing (it's the unique key)
                  />
                  {formMode === "edit" && (
                    <p className="text-xs text-muted-foreground">TVG ID cannot be changed when editing</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="display_name">Display Name (Optional)</Label>
                  <Input
                    id="display_name"
                    value={formData.display_name}
                    onChange={e => setFormData({...formData, display_name: e.target.value})}
                    placeholder="e.g. DAZN 1 ES"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="xmltv_url">XMLTV Source URL</Label>
                <Input
                  id="xmltv_url"
                  value={formData.xmltv_url}
                  onChange={e => setFormData({...formData, xmltv_url: e.target.value})}
                  placeholder="https://example.com/guide.xml"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="xmltv_channel_id">XMLTV Channel ID (If different from TVG ID)</Label>
                <Input
                  id="xmltv_channel_id"
                  value={formData.xmltv_channel_id}
                  onChange={e => setFormData({...formData, xmltv_channel_id: e.target.value})}
                  placeholder="e.g. M+.Liga.de.Campeones.es"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="ghost" onClick={resetForm}>Cancel</Button>
                <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                  {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {formMode === "edit" ? "Update Monitor" : "Save Monitor"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
          ) : !monitors || monitors.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Globe className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No linear monitors configured yet.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Channel</TableHead>
                  <TableHead>TVG ID</TableHead>
                  <TableHead>XMLTV URL</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {monitors.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.display_name || m.tvg_id}</TableCell>
                    <TableCell><code className="text-xs bg-muted px-1 rounded">{m.tvg_id}</code></TableCell>
                    <TableCell className="max-w-[300px] truncate text-xs text-muted-foreground">{m.xmltv_url}</TableCell>
                    <TableCell>
                      <Badge variant={m.enabled ? "default" : "secondary"}>
                        {m.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(m)}
                          title="Edit monitor"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleClone(m)}
                          title="Clone monitor"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                          onClick={() => {
                            if (confirm("Delete this monitor?")) deleteMutation.mutate(m.id)
                          }}
                          title="Delete monitor"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
