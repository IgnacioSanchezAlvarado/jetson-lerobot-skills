# Jetson LeRobot Demo — AI Coding Assistant Skills

Reusable skills and operational guides for the LeRobot SO-101 AWS Sim2Real2Sim demo. Works with both **Claude Code** and **Amazon Kiro**.

## What's Inside

```
.claude/commands/          # Claude Code slash commands
  demo-setup.md            #   /demo-setup — pre-flight check at venues
  deploy.md                #   /deploy — full deployment guide

.kiro/hooks/               # Kiro manual-trigger hooks
  demo-setup.kiro.hook     #   triggers #demo-setup steering
  deploy.kiro.hook         #   triggers #deploy steering

.kiro/steering/            # Kiro steering files (instructions)
  demo-setup.md            #   pre-flight check flow (manual)
  deploy.md                #   deployment flow (manual)
  product.md               #   project context (auto-loaded)

operations/                # Reference: LeRobot commands + demo platform
set-up/                    # Reference: Jetson setup, SSH, training
troubleshooting/           # Reference: GR00T, cameras, edge backend
```

## Usage

### Claude Code
Clone this repo into your project or copy the `.claude/` folder + reference docs:
```bash
# From your project root
/demo-setup    # Run pre-flight checks
/deploy        # Walk through full deployment
```

### Amazon Kiro
Clone this repo and open it as a workspace (or copy `.kiro/` + reference docs):
- `product.md` steering loads automatically for project context
- Trigger **Demo Pre-Flight Check** or **Full Deployment** from the Agent Hooks panel
- Or type `#demo-setup` / `#deploy` in chat to load the steering manually

## Prerequisites

- SSH access to the Jetson (aliases `jetson`, `jetson-eth`, `jetson-usb` in `~/.ssh/config`)
- `aws-pai` CLI installed (`pip install -e ".[dev]"` from the main project repo)
- AWS credentials configured for the target account

## Customization

These skills reference a specific EC2 instance ID and config structure. Update the following for your setup:
- Instance ID in `demo-setup` cloud access section
- SSH aliases/usernames in your `~/.ssh/config`
- Config paths if your project uses different locations
