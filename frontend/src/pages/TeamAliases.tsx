import { useState } from "react"
import { Plus, Trash2, Download, Upload, Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import {
  useAliases,
  useCreateAlias,
  useDeleteAlias,
  exportAliases,
  useImportAliases,
} from "@/api/aliases"
import type { TeamAliasCreate } from "@/api/types"

export function TeamAliases() {
  const [leagueFilter, setLeagueFilter] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState("")
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [newAlias, setNewAlias] = useState<TeamAliasCreate>({
    alias: "",
    league: "",
    team_id: "",
    team_name: "",
    provider: "espn",
  })

  const { data, isLoading } = useAliases(leagueFilter || undefined)
  const createMutation = useCreateAlias()
  const deleteMutation = useDeleteAlias()
  const importMutation = useImportAliases()

  // Get unique leagues for filter dropdown
  const leagues = [...new Set(data?.aliases.map((a) => a.league) || [])]

  // Filter by search query
  const filteredAliases = (data?.aliases || []).filter((alias) => {
    const query = searchQuery.toLowerCase()
    return (
      alias.alias.toLowerCase().includes(query) ||
      alias.team_name.toLowerCase().includes(query) ||
      alias.league.toLowerCase().includes(query)
    )
  })

  const handleCreate = async () => {
    try {
      await createMutation.mutateAsync(newAlias)
      setIsCreateOpen(false)
      setNewAlias({
        alias: "",
        league: "",
        team_id: "",
        team_name: "",
        provider: "espn",
      })
    } catch {
      // Error shown by mutation
    }
  }

  const handleExport = async () => {
    try {
      const aliases = await exportAliases()
      const blob = new Blob([JSON.stringify(aliases, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "team_aliases.json"
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error("Export failed:", e)
    }
  }

  const handleImport = () => {
    const input = document.createElement("input")
    input.type = "file"
    input.accept = ".json"
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      try {
        const text = await file.text()
        const aliases = JSON.parse(text)
        await importMutation.mutateAsync(aliases)
      } catch (e) {
        console.error("Import failed:", e)
      }
    }
    input.click()
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Team Aliases</h1>
          <p className="text-muted-foreground">
            Define custom name mappings for stream matching
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button variant="outline" onClick={handleImport}>
            <Upload className="h-4 w-4 mr-2" />
            Import
          </Button>
          <Button onClick={() => setIsCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Alias
          </Button>
        </div>
      </div>

      {/* Create Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent onClose={() => setIsCreateOpen(false)}>
          <DialogHeader>
            <DialogTitle>Create Team Alias</DialogTitle>
            <DialogDescription>
              Map a stream name to a provider team for better matching
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="alias">Alias Text</Label>
              <Input
                id="alias"
                value={newAlias.alias}
                onChange={(e) => setNewAlias({ ...newAlias, alias: e.target.value })}
                placeholder="e.g., Spurs, Man U, NYG"
              />
              <p className="text-xs text-muted-foreground">
                The text that appears in stream names
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="league">League Code</Label>
              <Input
                id="league"
                value={newAlias.league}
                onChange={(e) => setNewAlias({ ...newAlias, league: e.target.value })}
                placeholder="e.g., eng.1, nfl, nba"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="team_name">Team Name</Label>
              <Input
                id="team_name"
                value={newAlias.team_name}
                onChange={(e) => setNewAlias({ ...newAlias, team_name: e.target.value })}
                placeholder="e.g., Tottenham Hotspur"
              />
              <p className="text-xs text-muted-foreground">
                The full team name from the provider
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="team_id">Team ID</Label>
              <Input
                id="team_id"
                value={newAlias.team_id}
                onChange={(e) => setNewAlias({ ...newAlias, team_id: e.target.value })}
                placeholder="e.g., 367"
              />
              <p className="text-xs text-muted-foreground">
                The provider's team ID (find in Team Import or API)
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="provider">Provider</Label>
              <Select
                id="provider"
                value={newAlias.provider}
                onChange={(e) => setNewAlias({ ...newAlias, provider: e.target.value })}
              >
                <option value="espn">ESPN</option>
                <option value="tsdb">TheSportsDB</option>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={
                !newAlias.alias ||
                !newAlias.league ||
                !newAlias.team_id ||
                !newAlias.team_name ||
                createMutation.isPending
              }
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader>
          <CardTitle>Aliases ({filteredAliases.length})</CardTitle>
          <CardDescription>
            Aliases are checked before fuzzy matching for higher precision
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search aliases..."
                className="pl-10"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select
              className="w-48"
              value={leagueFilter}
              onChange={(e) => setLeagueFilter(e.target.value)}
            >
              <option value="">All Leagues</option>
              {leagues.map((league) => (
                <option key={league} value={league}>
                  {league}
                </option>
              ))}
            </Select>
          </div>

          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : filteredAliases.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchQuery || leagueFilter ? "No aliases match your filters" : "No aliases defined yet"}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Alias</TableHead>
                  <TableHead>League</TableHead>
                  <TableHead>Team Name</TableHead>
                  <TableHead>Team ID</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAliases.map((alias) => (
                  <TableRow key={alias.id}>
                    <TableCell className="font-medium">{alias.alias}</TableCell>
                    <TableCell>
                      <code className="bg-muted px-1 py-0.5 rounded text-sm">{alias.league}</code>
                    </TableCell>
                    <TableCell>{alias.team_name}</TableCell>
                    <TableCell className="font-mono text-sm">{alias.team_id}</TableCell>
                    <TableCell className="capitalize">{alias.provider}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteMutation.mutate(alias.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>How It Works</CardTitle>
        </CardHeader>
        <CardContent className="prose prose-sm dark:prose-invert max-w-none">
          <p>
            Team aliases help with stream matching when automatic fuzzy matching fails.
            Common use cases:
          </p>
          <ul>
            <li>
              <strong>Nicknames:</strong> "Spurs" → "Tottenham Hotspur" (EPL) or "San Antonio Spurs" (NBA)
            </li>
            <li>
              <strong>Abbreviations:</strong> "Man U" → "Manchester United"
            </li>
            <li>
              <strong>Local Names:</strong> "NYG" → "New York Giants"
            </li>
          </ul>
          <p>
            Aliases are league-specific so "Spurs" can map to different teams in different leagues.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
