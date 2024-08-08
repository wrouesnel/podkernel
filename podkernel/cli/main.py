import base64
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict

import click
import colorama
import structlog
from click.decorators import pass_meta_key
from podman import PodmanClient

from podkernel.kernelspec import user_kernelspec_store, make_kernel_id, install_kernelspec, validate_kernel_id, \
    KERNELSPEC_FILENAME
from podkernel.models import JupyterKernelSpec, JupyterInterruptMode, PodKernelMetadata
from ..logging import configure_logging, get_logger

logger = get_logger()

ENV_PREFIX = "PODKERNEL"

# Namespace in the Jupyterlab kernel metadata key we use to store data. This is also used
# for temporary file names.
NAMESPACE = "podkernel"

# Try and support DOCKERNEL_CONNECTION_FILE which this is inspired by too
CONTAINER_CONNECTION_SPEC_PATH = "/kernel-connection-spec.json"
CONTAINER_CONNECTION_SPEC_ENV_VARS = (f"{ENV_PREFIX}_CONNECTION_FILE", "DOCKERNEL_CONNECTION_FILE")

JUPYTER_CONNECTION_FILE_TEMPLATE = "{connection_file}"

META_SYSTEM_TYPE = "system_type"
pass_system_type = pass_meta_key(META_SYSTEM_TYPE, doc_description="Current Python system type")

META_KERNEL_SPEC_DIR = "kernel_spec_dir"
pass_kernel_spec_dir = pass_meta_key(
    META_KERNEL_SPEC_DIR, doc_description="Jupyter kernel spec dir for the current user"
)

META_CONTAINER_CMD = "container_cmd"
pass_container_command = pass_meta_key(
    META_CONTAINER_CMD, doc_description="Command for invoking container operations"
)

@click.group("podkernel", context_settings={"show_default": True})
@click.option("--log-level", default="debug", help="Log level")
@click.option("--log-format", default="console", help="Log format output")
@click.option("--log-dest", default="stderr", help="Log output")
@click.option("--system-type", default=platform.system(), hidden=True, help="Hidden option to override system type")
@click.option("--container-command", default="podman", hidden=True, help="Hidden option to override container command")
@click.pass_context
def cli(ctx: click.Context, log_level: str, log_format: str, log_dest: str, system_type: str, container_command: str):
    """Manage Jupyter kernels in Podman containers"""
    configure_logging(log_level, log_format, log_dest)
    logger.debug("Logging Configured", log_level=log_level, log_format=log_format, log_dest=log_dest)

    logger.debug("System Type Set", system_type=system_type)
    ctx.meta[META_SYSTEM_TYPE] = system_type
    ctx.meta[META_KERNEL_SPEC_DIR] = user_kernelspec_store(system_type)
    ctx.meta[META_CONTAINER_CMD] = container_command

def _common_list(kernel_spec_dir: Path) -> Dict[str,Any]:
    podkernels = {}
    for item in kernel_spec_dir.iterdir():
        if not item.is_dir():
            continue
        kernel_specfile = (item / KERNELSPEC_FILENAME)
        if not kernel_specfile.exists():
            continue
        kernelspec = json.loads(kernel_specfile.read_text())
        if NAMESPACE in kernelspec.get("metadata", {}):
            podkernels[item.name] = kernelspec
    return podkernels

@cli.command("list")
@pass_kernel_spec_dir
def cli_list(kernel_spec_dir: Path):
    """List installed podkernels"""
    for kernel_id, kernelspec in _common_list(kernel_spec_dir).items():
        click.echo(f"{kernel_id}\t{kernelspec['display_name']}")

@cli.command("delete")
@click.option("--doit/--dryrun", default=False, type=click.BOOL, help="Actually delete the kernel")
@click.argument("kernel_id", type=click.STRING)
@pass_kernel_spec_dir
def cli_delete(kernel_spec_dir: Path, doit: bool, kernel_id: str):
    """Delete an installed podkernel"""
    log = logger.bind(kernel_id=kernel_id)
    kernel_specs = _common_list(kernel_spec_dir)
    if kernel_id not in kernel_specs:
        raise click.ClickException(f"No kernel ID with that name exists: {kernel_id}")
    kernelspec = (kernel_spec_dir / kernel_id)
    if not kernelspec.is_dir():
        raise click.ClickException(f"Found kernelspec but it is not a directory as expected: {kernel_id}")
    kernel_specfile = kernelspec / KERNELSPEC_FILENAME
    if not kernel_specfile.exists():
        raise click.ClickException(f"No kernel.json file in the target directory ID: {kernel_id}")
    log = log.bind(kernel_specdir=kernelspec.as_posix())
    if doit:
        log.info("Removing kernel spec")
        shutil.rmtree(kernelspec)
    else:
        log.info("DRY RUN: pass --doit to action")


@cli.command("install")
@click.option("--display-name", type=click.STRING, help="Display name for the kernel")
@click.option("--language", default="python", type=click.STRING, help="Specify the language the kernel is for")
@click.option("--build/--image", type=click.BOOL, default=False, help="Image name is a path to a Dockerfile folder")
@click.argument("image_name", nargs=1, type=click.STRING)
@click.argument("arguments", nargs=-1, type=click.STRING)
@pass_kernel_spec_dir
def cli_install(kernel_spec_dir: Path, display_name: str,
    build: bool, language: str, image_name: str, arguments: List[str]
):
    """Install a new kernel

    Specifying either a container image name, or pass the --build option and specify
    a path to a directory containing a Containerfile/Dockerfile.

    ARGUMENTS should either be of the form:

      [podman run args] -- [container command args]

    or if --build is specified:

      [podman build args] -- [podman run args] -- [container command args]
    """
    log = logger

    if build:
        # Check if the path is under $HOME and store it relatively if so. Otherwise, absolute.
        build_path = Path(image_name).absolute().resolve()
        home_dir = Path("~").expanduser().resolve()
        try:
            build_path = build_path.relative_to(home_dir)
            build_path = Path("~") / build_path
            log.debug("Directory path is not in user home directory - storing as relative path")
        except ValueError:
            log.debug("Directory path is not in user home directory - storing as absolute path")
            pass
        image_name = build_path.as_posix()

    log = log.bind(image_name=image_name)
    log.debug("Image name set")

    if display_name is None:
        log.debug("Automatically determine a display name")
        name = image_name if not build else Path(image_name).name
        display_name = f"{name} ({language})"
    log = log.bind(display_name=display_name)
    log.info("Display name set")

    log.debug("Process arguments list", arguments=arguments)

    # These are the argument sections we know
    build_args = []
    run_args = []
    cmd_args = []

    # arg_order helps us process the list and log what we got too
    arg_order = [("run_args", run_args), ("cmd_args", cmd_args)]
    if build:
        arg_order.insert(0, ("build_args", build_args))
    arg_name, cur_args = arg_order.pop(0)
    log.debug("Parsing argument section", arg_name=arg_name)
    for argument in arguments:
        if argument == "--":
            if len(arg_order) > 0:
                arg_name, cur_args = arg_order.pop(0)
                log.debug("Separate found - new argument run", arg_name=arg_name)
                continue
            else:
                log.warn("Found an argument separator but no more sections. Did you mix up your argument?",
                         arg_name=arg_name)
        # Just append the argument to the section
        cur_args.append(argument)

    log.info("Validating argument lists")
    arg_list_has_errors = False
    log.debug("Validating build_args")
    if any( value.startswith("--iidfile") for value in build_args ):
        logger.error(f"build_args cannot include --iidfile as it will be overridden on execution")
        arg_list_has_errors = True

    log.debug("Validating run_args")
    disallowed_run_args = {
        "--rm",
        "-d",
        "--detach",
        "-i",
        "--interactive",
        "-t",
        "--tty",
        "-a",
        "--attach",
    }
    for value in run_args:
        if value.startswith("--rm"):
            logger.error(f"run_args cannot contain {value} as it will be overridden on execution")
            arg_list_has_errors = True
            continue

        if value in disallowed_run_args:
            logger.error(f"run_args cannot contain {value} as it will be overriden on execution")
            arg_list_has_errors = True
            continue

    if arg_list_has_errors:
        raise click.ClickException("Supplied argument lists have options which are not allowed - check error messages.")

    log.debug("Build podkernel metadata")
    kernel_meta = PodKernelMetadata(
        image_name=image_name,
        build=build,
        build_args=build_args,
        run_args=run_args,
        cmd_args=cmd_args,
    )

    log.debug("Generate unique kernel ID based on metadata")
    hashtag = base64.urlsafe_b64encode(hashlib.sha256(kernel_meta.model_dump_json(indent=False).encode("utf8")).digest()).decode()
    kernel_id = make_kernel_id(f"{image_name.lstrip('~/')}-{hashtag.rstrip('=')}")
    validate_kernel_id(kernel_id)
    log = log.bind(kernel_id=kernel_id)

    log.debug("Build kernelspec")
    kernelspec = JupyterKernelSpec(
        argv=[NAMESPACE, cli_start.name, kernel_id, JUPYTER_CONNECTION_FILE_TEMPLATE],
        display_name=display_name,
        language=language,
        interrupt_mode=JupyterInterruptMode.Message,
        metadata={
            NAMESPACE: kernel_meta.model_dump(),
        },
    )

    kernel_dir = kernel_spec_dir / kernel_id
    kernel_specfile = kernel_dir / KERNELSPEC_FILENAME
    log = log.bind(kernel_specfile=kernel_specfile.as_posix())

    log.debug("Check if kernelspec already exists")
    if kernel_specfile.exists():
        existing_spec = JupyterKernelSpec.model_validate_json(kernel_specfile.read_text())
        log.info("Identical kernel already exists", existing_display_name=existing_spec.display_name, existing_language=existing_spec.language)
        sys.exit(0)

    log.info("Installing new kernel")
    kernel_dir.mkdir(parents=True, exist_ok=True)
    kernel_specfile.write_text(kernelspec.model_dump_json(indent=True, exclude_unset=True))
    log.info("New kernel installed")

def _common_startup(container_cmd: str, kernel_spec_dir: Path, kernel_id: str) -> Tuple[structlog.BoundLogger, str, JupyterKernelSpec, PodKernelMetadata]:
    """Common startup for commands handling kernel specs

    This function updates the logger and returns the container exe, parsed kernel spec and podkernel metadata.
    """
    log = logger.bind(kernel_id=kernel_id)

    log.debug("Discovering container command", container_cmd=container_cmd)
    container_exe = shutil.which(container_cmd)
    log = log.bind(container_exe=container_exe)

    kernel_dir = kernel_spec_dir / kernel_id
    kernel_specfile = kernel_dir / KERNELSPEC_FILENAME
    log.debug("Loading kernel spec", kernel_specfile=kernel_specfile.as_posix())
    existing_spec = JupyterKernelSpec.model_validate_json(kernel_specfile.read_text())
    log.debug("Kernel spec parsed successfully")

    log.debug("Loading pod kernel metadata")
    kernel_meta = PodKernelMetadata.model_validate(existing_spec.metadata[NAMESPACE])
    log = log.bind(image_name=kernel_meta.image_name, build=kernel_meta.build)
    log.debug("Pod kernel metadata parsed successfully")

    return log, container_exe, existing_spec, kernel_meta

def _inspect_image(container_exe: str, kernel_meta: PodKernelMetadata) -> Optional[str]:
    """Inspect an image using the command line"""
    try:
        inspect_result = subprocess.check_output([container_exe, "inspect", kernel_meta.image_name], encoding="utf8")
    except subprocess.CalledProcessError as e:
        inspect_result = e.output
    inspect_obj = json.loads(inspect_result)
    if len(inspect_obj) == 0:
        return None
    return inspect_obj[0]["Id"]

def _common_build(log: structlog.BoundLogger, kernel_id: str, container_exe: str, kernel_meta: PodKernelMetadata, pull=False) -> Optional[str]:
    """Build a configured kernel"""
    image_id = None

    if kernel_meta.build:
        log.info("Building image")
        with tempfile.NamedTemporaryFile(prefix=f"{NAMESPACE}.{kernel_id}.", suffix=".iid", mode="rt",
                                         delete=True) as iidfile:
            build_cmd = [container_exe, "build"] + kernel_meta.build_args + ["--iidfile", iidfile.name] + [
                Path(kernel_meta.image_name).expanduser().as_posix()]
            log.debug("Executing command", build_cmd=build_cmd)
            subprocess.check_call(build_cmd)
            image_id = iidfile.readline()
            log.debug("Read image ID from file", image_id=image_id, iidfile=iidfile.name)
    else:
        log.debug("Inspecting container image ID")
        image_id = _inspect_image(container_exe, kernel_meta)
        if image_id is None and pull:
            log.info("Image not found - attempting to pull image")
            try:
                subprocess.run([container_exe, "pull", kernel_meta.image_name])
            except subprocess.CalledProcessError as e:
                log.error("Error pulling container image", retcode=e.returncode)
            image_id = _inspect_image(container_exe, kernel_meta)
            if image_id is None:
                log.error("Image still not found after attempting pull.")

        if image_id is not None:
            log.debug("Read image ID from inspect result", image_id=image_id, image_name=kernel_meta.image_name)
        else:
            log.error("Image not found")

    return image_id

@cli.command("build")
@click.argument("kernel_id", type=click.STRING)
@pass_kernel_spec_dir
@pass_container_command
def cli_build(container_cmd: str, kernel_spec_dir: Path, kernel_id: str):
    """Build a kernel and return the ID

    For non-build kernels, this will trigger an image pull which can be useful if you
    do not run your images with --pull=always as a run argument.
    """
    log, container_exe, existing_spec, kernel_meta = _common_startup(container_cmd, kernel_spec_dir, kernel_id)
    image_id = _common_build(log, kernel_id, container_exe, kernel_meta)
    if image_id is None:
        raise click.ClickException("Image build failed")
    click.echo(colorama.Fore.LIGHTGREEN_EX + image_id + colorama.Style.RESET_ALL)

@cli.command("start")
@click.argument("kernel_id", type=click.STRING)
@click.argument("connection_file", type=click.STRING)
@pass_kernel_spec_dir
@pass_container_command
def cli_start(container_cmd: str, kernel_spec_dir: Path, kernel_id: str, connection_file: str):
    """Start a kernel"""

    log, container_exe, existing_spec, kernel_meta = _common_startup(container_cmd, kernel_spec_dir, kernel_id)

    image_id = _common_build(log, kernel_id, container_exe, kernel_meta)
    if image_id is None:
        raise click.ClickException("Failed to acquire the image ID during container startup - see above logs")

    log.info("Current directory", curdir=Path(".").resolve())

    log.debug("Reading connection file for container")
    connection_obj = json.loads(Path(connection_file).read_text())
    connection_obj["ip"] = "0.0.0.0"
    connection_ports = {v for k,v in connection_obj.items() if "_port" in k}

    log.debug("Updating connection file for container")
    Path(connection_file).write_text(json.dumps(connection_obj, indent=True))

    # Add the additional arguments
    control_args = [
        "--rm",
        "-v", f"{Path(connection_file).absolute().as_posix()}:{CONTAINER_CONNECTION_SPEC_PATH}:ro"
    ]

    # Add the environment variables
    for env_var in CONTAINER_CONNECTION_SPEC_ENV_VARS:
        control_args.extend(["-e", f"{env_var}={CONTAINER_CONNECTION_SPEC_PATH}",])

    # Add the port mappings
    for port in sorted(connection_ports):
        control_args.extend(["-p", f"127.0.0.1:{port}:{port}"])

    run_cmd = [container_exe, "run", ] + kernel_meta.run_args + control_args + [image_id] + kernel_meta.cmd_args
    log.info("Starting container", run_cmd=run_cmd)

    p = subprocess.Popen(run_cmd)
    log.info("Container started - waiting for exit")
    retcode = p.wait()
    log.info("Container exited", retcode=retcode)
    sys.exit(retcode)

def main():
    cli(auto_envvar_prefix=ENV_PREFIX)


if __name__ == "__main__":
    main()
