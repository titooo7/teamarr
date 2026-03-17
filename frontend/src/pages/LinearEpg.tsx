import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { RefreshCw, Loader2, Globe, Tv, Calendar, CheckCircle2, XCircle, Save, Filter } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { getDispatcharrSettings, updateDispatcharrSettings } from "@/api/settings"

interface LinearChannel {
  tvg_id: string
  channel_ids: number[]
}

interface Programme {
  id: number
  tvg_id: string
  title: string | null
  subtitle: string | null
  start_time: string
  end_time: string
  channel_ids: number[]
}

export function LinearEpg() {
  const queryClient = useQueryClient()
  const [selectedChannels, setSelectedChannels] = useState<string[]>([])
  const [hasInitialized, setHasInitialized] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  // Fetch settings to get currently filtered channels
  const { data: settings, isSuccess: settingsLoaded } = useQuery({
    queryKey: ["settings", "dispatcharr"],
    queryFn: getDispatcharrSettings
  })

  // Initialize selection from settings once when loaded
  useEffect(() => {
    if (settingsLoaded && settings?.discovery_channels && !hasInitialized) {
      setSelectedChannels(settings.discovery_channels)
      setHasInitialized(true)
    }
  }, [settingsLoaded, settings, hasInitialized])

  // Fetch unique channels from cache
  const { data: channels, isLoading: channelsLoading } = useQuery<LinearChannel[]>({
    queryKey: ["linear-channels"],
    queryFn: async () => {
      const resp = await fetch("/api/v1/linear-epg/channels")
      if (!resp.ok) throw new Error("Failed to fetch linear channels")
      return resp.json()
    }
  })

  // Fetch programmes from cache
  const { data: programmes, isLoading: programmesLoading } = useQuery<Programme[]>({
    queryKey: ["linear-programmes"],
    queryFn: async () => {
      const resp = await fetch("/api/v1/linear-epg/programmes")
      if (!resp.ok) throw new Error("Failed to fetch programmes")
      return resp.json()
    }
  })

  // Update settings mutation
  const saveSettingsMutation = useMutation({
    mutationFn: (channels: string[]) => updateDispatcharrSettings({ discovery_channels: channels }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "dispatcharr"] })
      toast.success("Discovery filters saved. Run refresh to apply.")
    },
    onError: (error: any) => {
      toast.error(`Failed to save: ${error.message}`)
    }
  })

  // Refresh cache mutation
  const refreshMutation = useMutation({
    mutationFn: async () => {
      const resp = await fetch("/api/v1/linear-epg/refresh", { method: "POST" })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || "Failed to trigger refresh")
      }
      return resp.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["linear-channels"] })
      queryClient.invalidateQueries({ queryKey: ["linear-programmes"] })
      toast.success("Linear EPG refresh complete")
    },
    onError: (error: any) => {
      toast.error(`Refresh failed: ${error.message}`)
    }
  })

  const toggleChannel = (tvgId: string) => {
    setSelectedChannels(prev => 
      prev.includes(tvgId) 
        ? prev.filter(id => id !== tvgId)
        : [...prev, tvgId]
    )
  }

  const isSelected = (tvgId: string) => {
    // If list is empty, all are active
    if (selectedChannels.length === 0) return true
    return selectedChannels.includes(tvgId)
  }

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString([], {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch (e) {
      return isoString
    }
  }

  const filteredChannels = channels?.filter(ch => 
    ch.tvg_id.toLowerCase().includes(searchQuery.toLowerCase())
  ) || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Linear EPG Discovery</h1>
          <p className="text-muted-foreground">
            Automatic discovery of sports events on your 24/7 Dispatcharr channels.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => saveSettingsMutation.mutate(selectedChannels)}
            disabled={saveSettingsMutation.isPending}
          >
            {saveSettingsMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save Filters
          </Button>
          <Button
            variant="default"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            {refreshMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh from Dispatcharr
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-1">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base">
                <Tv className="h-4 w-4" />
                Discovery Channels
              </CardTitle>
              <Badge variant="secondary" className="text-[10px]">
                {selectedChannels.length === 0 ? "All Active" : `${selectedChannels.length} Selected`}
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Select which channels to monitor for sports events.
            </CardDescription>
            <div className="relative mt-2">
              <Filter className="absolute left-2 top-2.5 h-3 w-3 text-muted-foreground" />
              <Input
                placeholder="Search TVG IDs..."
                className="pl-8 h-8 text-xs"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </CardHeader>
          <CardContent>
            {channelsLoading ? (
              <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
            ) : filteredChannels.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p className="text-sm">No channels found.</p>
              </div>
            ) : (
              <div className="space-y-1 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
                <div className="flex items-center space-x-2 p-2 rounded-md bg-muted/30 border border-dashed mb-2">
                  <Checkbox 
                    id="select-all" 
                    checked={selectedChannels.length === 0}
                    onCheckedChange={() => setSelectedChannels([])}
                  />
                  <label htmlFor="select-all" className="text-xs font-medium cursor-pointer">
                    Monitor All (Default)
                  </label>
                </div>
                {filteredChannels.map((ch) => (
                  <div 
                    key={ch.tvg_id} 
                    className={`flex items-center justify-between p-2 rounded-lg border transition-colors ${
                      isSelected(ch.tvg_id) ? 'bg-muted/50 border-primary/20' : 'bg-background opacity-60'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Checkbox 
                        id={`ch-${ch.tvg_id}`} 
                        checked={selectedChannels.includes(ch.tvg_id)}
                        onCheckedChange={() => toggleChannel(ch.tvg_id)}
                      />
                      <div className="flex flex-col">
                        <label htmlFor={`ch-${ch.tvg_id}`} className="text-xs font-medium font-mono cursor-pointer">{ch.tvg_id}</label>
                        <span className="text-[10px] text-muted-foreground">
                          {ch.channel_ids.length} Dispatcharr {ch.channel_ids.length === 1 ? 'channel' : 'channels'}
                        </span>
                      </div>
                    </div>
                    {isSelected(ch.tvg_id) ? (
                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                    ) : (
                      <XCircle className="h-3 w-3 text-muted-foreground" />
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Calendar className="h-4 w-4" />
              Cached Programmes
            </CardTitle>
            <CardDescription className="text-xs">
              Upcoming programmes for your selected discovery channels.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {programmesLoading ? (
              <div className="flex justify-center py-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
            ) : !programmes || programmes.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Globe className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p>No programmes discovered yet.</p>
                <p className="text-xs mt-2">Adjust filters and click Refresh.</p>
              </div>
            ) : (
              <div className="rounded-md border overflow-hidden">
                <Table>
                  <TableHeader className="bg-muted/50">
                    <TableRow>
                      <TableHead className="w-[120px] text-xs">TVG ID</TableHead>
                      <TableHead className="text-xs">Programme</TableHead>
                      <TableHead className="w-[180px] text-xs">Start Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {programmes.slice(0, 100).map((p) => (
                      <TableRow key={p.id}>
                        <TableCell>
                          <code className="text-[10px] bg-muted px-1 py-0.5 rounded border">{p.tvg_id}</code>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col text-xs">
                            <span className="font-medium line-clamp-1">{p.title}</span>
                            {p.subtitle && (
                              <span className="text-muted-foreground line-clamp-1">{p.subtitle}</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-[10px] text-muted-foreground">
                          {formatTime(p.start_time)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {programmes.length > 100 && (
                  <div className="p-2 text-center text-[10px] text-muted-foreground bg-muted/20 border-t italic">
                    Showing first 100 of {programmes.length} programmes. All are used for discovery matching.
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="bg-primary/5 border-primary/20">
        <CardHeader>
          <CardTitle className="text-sm">Discovery Optimization</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-4 text-muted-foreground">
          <p className="text-xs">
            To ensure games are found, make sure the <strong>TVG ID</strong> of the channels showing the games is in your discovery list.
          </p>
          <ul className="list-disc list-inside space-y-1 text-[10px]">
            <li>Select only the sports channels you want Teamarr to monitor.</li>
            <li>If a game isn't found on a Spanish channel, try adding the UK or Polish versions (e.g., <code>skysports</code>, <code>elevensports</code>).</li>
            <li>Check the logs after generating EPG to see potential matches being discovered.</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
