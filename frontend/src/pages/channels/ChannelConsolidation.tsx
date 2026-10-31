import { useState } from "react"
import { toast } from "sonner"
import { SaveButton } from "@/components/ui/save-button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { RadioCards } from "@/components/ui/radio-cards"
import { ExceptionKeywordsCard } from "@/components/ExceptionKeywordsCard"
import { RaceFeedsCard } from "@/components/RaceFeedsCard"
import { FeedSeparationCard } from "@/components/FeedSeparationCard"
import {
  useChannelNumberingSettings,
  useUpdateChannelNumberingSettings,
} from "@/hooks/useSettings"
import type { ChannelNumberingSettings } from "@/api/settings"

/**
 * Channels → Consolidation. How events/streams map to channels: the master
 * Consolidate/Separate default, plus the two carve-out mechanisms that split
 * channels apart — exception keywords and feed (home/away) separation.
 *
 * Stream Consolidation lives in the channel-numbering blob (full-PUT). This
 * page only edits global_consolidation_mode; numbering mode and per-league
 * starts (edited under Numbering) ride along untouched. Only one Channels view
 * mounts at a time, so the full-PUT is safe.
 */
export function ChannelConsolidation() {
  const { data: channelNumberingData } = useChannelNumberingSettings()
  const updateChannelNumbering = useUpdateChannelNumberingSettings()

  const [channelNumbering, setChannelNumbering] = useState<ChannelNumberingSettings>({
    global_channel_mode: "auto",
    league_channel_starts: {},
    global_consolidation_mode: "consolidate",
    channel_stability_mode: "compact",
    channel_gap_size: 3,
    channel_order_mode: "sport_league",
    channel_daily_reset_enabled: true,
    channel_daily_reset_time: "04:00",
    force_channel_relayout_pending: false,
    separate_fallback_enabled: false,
    separate_fallback_count: 3,
  })

  // Sync local state from the server data during render (React's "adjusting
  // state when a prop changes" pattern) — re-seeds on every refetch, exactly
  // like the previous effect, without the extra effect render pass.
  const [syncedChannelNumberingData, setSyncedChannelNumberingData] =
    useState<typeof channelNumberingData>(undefined)
  if (channelNumberingData && channelNumberingData !== syncedChannelNumberingData) {
    setSyncedChannelNumberingData(channelNumberingData)
    setChannelNumbering(channelNumberingData)
  }

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <CardTitle>Stream Consolidation</CardTitle>
          <CardDescription>
            When an event has multiple streams, merge them into one channel or split them apart
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <Label className="text-sm font-medium">Default Mode</Label>
            <RadioCards
              name="consolidation-mode"
              value={channelNumbering.global_consolidation_mode}
              onChange={(v) =>
                setChannelNumbering({ ...channelNumbering, global_consolidation_mode: v })
              }
              options={[
                {
                  value: "consolidate",
                  label: "Consolidate",
                  description:
                    "Merge multiple streams for the same event into one channel. Exception keywords can override per-stream.",
                },
                {
                  value: "separate",
                  label: "Separate",
                  description:
                    "Each stream gets its own channel. More channels, no merging.",
                },
              ]}
            />
          </div>

          {/* (fork) Separate-mode failover backups — rendered unconditionally:
              a per-keyword 'separate' behavior can make this active even
              while the default mode above reads "Consolidate". */}
          <div className="space-y-4 pl-2 border-l-2 border-muted ml-1">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Separate Mode Failover Backups</Label>
                <p className="text-xs text-muted-foreground">
                  Applies to any channel created in separate mode — the global mode above, or a
                  per-keyword Separate behavior. Each such channel additionally carries same-group
                  sibling streams behind its own stream as Dispatcharr failover backups.
                </p>
              </div>
              <Switch
                checked={channelNumbering.separate_fallback_enabled}
                onCheckedChange={(checked) =>
                  setChannelNumbering({ ...channelNumbering, separate_fallback_enabled: checked })
                }
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="separate-fallback-count">Backup Count</Label>
              <Input
                id="separate-fallback-count"
                type="number"
                min={0}
                max={10}
                disabled={!channelNumbering.separate_fallback_enabled}
                value={channelNumbering.separate_fallback_count}
                onChange={(e) =>
                  setChannelNumbering({
                    ...channelNumbering,
                    separate_fallback_count: Math.max(0, Math.min(10, Number(e.target.value) || 0)),
                  })
                }
                className="max-w-[8rem]"
              />
              <p className="text-xs text-muted-foreground">
                Up to this many same-keyword sibling streams per channel, behind its own stream
                (0-10, default 3)
              </p>
            </div>
          </div>

          <SaveButton
            onClick={async () => {
              try {
                await updateChannelNumbering.mutateAsync(channelNumbering)
                toast.success("Stream consolidation saved")
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Failed to save")
              }
            }}
            pending={updateChannelNumbering.isPending}
          />
        </CardContent>
      </Card>

      <ExceptionKeywordsCard />
      <RaceFeedsCard />
      <FeedSeparationCard />
    </div>
  )
}
