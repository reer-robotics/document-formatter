import argparse
import json
import sys

from .engine import Project, check, read_json, template_names


def main():
    parser = argparse.ArgumentParser(
        description="Source-linked document formatting with optional local Ollama synthesis"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("project")
    p.add_argument("--template", default="technical-report")
    p.add_argument("--title", default="Untitled document")
    p = sub.add_parser("ingest")
    p.add_argument("project")
    p.add_argument("inputs", nargs="+")
    p = sub.add_parser("propose")
    p.add_argument("project")
    p.add_argument("--model")
    p.add_argument("--vision-model")
    p.add_argument("--endpoint", default="http://127.0.0.1:11434")
    p = sub.add_parser("accept")
    p.add_argument("project")
    p.add_argument("--proposal-id", required=True)
    p = sub.add_parser("edit")
    p.add_argument("project")
    p.add_argument("--document-json", required=True)
    p = sub.add_parser("check")
    p.add_argument("project")
    sub.add_parser("templates")
    p = sub.add_parser("serve")
    p.add_argument("--workspace", default="workspace")
    p.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    try:
        if args.command == "templates":
            print("\n".join(template_names()))
        elif args.command == "serve":
            from .server import create_app

            create_app(args.workspace).run(
                host="127.0.0.1", port=args.port, debug=False, threaded=False
            )
        elif args.command == "init":
            Project.create(args.project, args.template, args.title)
            print("Project initialized")
        elif args.command == "ingest":
            print(json.dumps(Project(args.project).ingest(args.inputs)))
        elif args.command == "propose":
            proposal = Project(args.project).propose(
                args.model, args.vision_model, args.endpoint
            )
            print(
                json.dumps(
                    {
                        "proposal_id": proposal["id"],
                        "mode": proposal["mode"],
                        "checks": proposal["checks"],
                        "warnings": proposal["warnings"],
                    },
                    indent=2,
                )
            )
        elif args.command == "accept":
            Project(args.project).accept(args.proposal_id)
            print("Accepted; document.md and revision history saved")
        elif args.command == "edit":
            Project(args.project).edit(read_json(args.document_json))
            print("Manual edit saved")
        elif args.command == "check":
            state = Project(args.project).load()
            if not state["document"]:
                raise ValueError("Accept a proposal first")
            issues = check(state["document"], state["template"], state["sources"])
            print(json.dumps(issues, indent=2))
            return 1 if issues else 0
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
