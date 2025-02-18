import argparse
import asyncio
from typing import List, Optional

from adoption import TemplateAdoptionTracker
from client import AzureDevOpsClient
from model import AdoptionTarget, TemplateSource
from print import ViewMode, print_adoption_results


def create_target(
    project_name: str,
    repository_name: Optional[str] = None,
    pipeline_id: Optional[int] = None,
) -> AdoptionTarget:
    """Creates an AdoptionTarget from CLI arguments."""
    return AdoptionTarget(
        project_name=project_name,
        repository_name=repository_name,
        pipeline_id=pipeline_id,
    )


def create_source(
    project: str,
    repository: str,
    template_path: Optional[str] = None,
    directories: Optional[List[str]] = None,
    branch: str = "main",
) -> TemplateSource:
    """Creates a TemplateSource from CLI arguments."""
    return TemplateSource(
        project=project,
        repository=repository,
        template_path=template_path,
        directories=directories or ["/"],
        branch=branch,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Track Azure DevOps pipeline template adoption"
    )

    # Azure DevOps connection
    parser.add_argument(
        "--organization", required=True, help="Azure DevOps organization name"
    )
    parser.add_argument("--token", help="Azure DevOps PAT token")

    # Target configuration
    target_group = parser.add_argument_group(
        "target", "Where to look for template adoption"
    )
    target_group.add_argument(
        "--target-project", required=True, help="Target project name"
    )
    target_mutex_group = target_group.add_mutually_exclusive_group()
    target_mutex_group.add_argument(
        "--target-repository",
        help="Optional target repository name (ignored if pipeline ID is provided)",
    )
    target_mutex_group.add_argument(
        "--target-pipeline-id", type=int, help="Optional target pipeline ID"
    )

    # Template source configuration
    source_group = parser.add_argument_group("source", "Template source configuration")
    source_group.add_argument(
        "--source-project", required=True, help="Template source project"
    )
    source_group.add_argument(
        "--source-repository", required=True, help="Template source repository"
    )
    source_group.add_argument(
        "--source-branch", default="main", help="Template source branch (default: main)"
    )
    source_mutex_group = source_group.add_mutually_exclusive_group()
    source_mutex_group.add_argument(
        "--source-template", help="Specific template path to track"
    )
    source_mutex_group.add_argument(
        "--source-directories",
        nargs="+",
        help="List of directories containing templates to track",
    )

    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    """Run the adoption tracker with CLI arguments."""
    # Create target and source configurations
    target = create_target(
        project_name=args.target_project,
        repository_name=args.target_repository,
        pipeline_id=args.target_pipeline_id,
    )

    source = create_source(
        project=args.source_project,
        repository=args.source_repository,
        template_path=args.source_template,
        directories=args.source_directories,
        branch=args.source_branch,
    )

    # Create and run tracker
    async with AzureDevOpsClient(
        organization=args.organization,
        project=target.project_name,
        token=args.token,
    ) as client:
        tracker = TemplateAdoptionTracker(
            client=client,
            target=target,
            template_source=source,
        )

        result, metrics = await tracker.track()
        print_adoption_results(result, metrics, ViewMode.TARGET)


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()
    asyncio.run(run(args))
