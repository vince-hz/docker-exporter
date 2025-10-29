#region generated meta
import typing
class Inputs(typing.TypedDict):
    image_name: str
    platform: str
    output_path: str
class Outputs(typing.TypedDict):
    export_path: typing.NotRequired[str]
    image_id: typing.NotRequired[str]
    image_size: typing.NotRequired[float]
    export_format: typing.NotRequired[str]
#endregion

import subprocess
import os
import logging
import tarfile
from pathlib import Path
from oocana import Context

def main(params: Inputs, context: Context) -> Outputs:
    """
    Download Docker image with specific architecture and export as tar file or folder using skopeo

    Args:
        params: Input parameters containing image name, architecture, and output path
        context: OOMOL context object

    Returns:
        Dictionary containing export path, image ID, size, and export format
    """
    try:
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # Check if skopeo is installed
        try:
            subprocess.run(["skopeo", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise Exception(
                "skopeo is not installed. Please install it first:\n"
                "• On Ubuntu/Debian: sudo apt-get install skopeo\n"
                "• On CentOS/RHEL: sudo yum install skopeo\n"
                "• On macOS: brew install skopeo\n"
                "• Or download from: https://github.com/containers/skopeo"
            )

        image_name = params["image_name"]
        platform = params["platform"]
        output_path = params["output_path"]

        # Smart path detection based on input
        if output_path.lower().endswith('.tar'):
            # Direct tar file export mode - user specified tar file
            final_output_path = output_path
            export_format = "tar"
            output_mode = "direct_file"
            logger.info(f"Direct tar file export mode")
        elif output_path.endswith('/') or output_path.endswith('\\') or (os.path.exists(output_path) and os.path.isdir(output_path)):
            # Directory mode - path ends with slash, is existing directory, or looks like directory name
            clean_image_name = image_name.replace(':', '_').replace('/', '_')
            final_output_path = os.path.join(output_path.rstrip('/\\'), clean_image_name + ".tar")
            export_format = "tar"
            output_mode = "directory"
            logger.info(f"Directory mode: creating tar file with image name")
        elif not any(c in os.path.basename(output_path) for c in ['.',]):
            # Directory mode - no file extension, treat as directory
            clean_image_name = image_name.replace(':', '_').replace('/', '_')
            final_output_path = os.path.join(output_path, clean_image_name + ".tar")
            export_format = "tar"
            output_mode = "directory"
            logger.info(f"Directory mode: no extension detected, treating as directory")
        else:
            # Direct file export mode - user specified file
            final_output_path = output_path
            export_format = "folder" if not output_path.lower().endswith('.tar') else "tar"
            output_mode = "direct_file"
            logger.info(f"Direct file export mode")

        logger.info(f"Downloading Docker image: {image_name} for platform: {platform}")
        logger.info(f"Output mode: {output_mode}")
        logger.info(f"Input path: {output_path}")
        logger.info(f"Final output path: {final_output_path}")
        logger.info(f"Export format: {export_format}")

        # Ensure output directory exists
        if export_format == "folder":
            output_dir = final_output_path
        else:
            output_dir = os.path.dirname(final_output_path)

        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Remove existing file if it exists (docker-archive doesn't support overwriting)
        if export_format == "tar" and os.path.exists(final_output_path):
            os.remove(final_output_path)
            logger.info(f"Removed existing tar file: {final_output_path}")

        # Build skopeo command with platform override if specified
        skopeo_cmd = ["skopeo", "copy"]

        # Add platform override if specified
        if platform and platform.lower() != "all":
            skopeo_cmd.extend(["--override-os", platform.split("/")[0]])
            if "/" in platform:
                skopeo_cmd.extend(["--override-arch", platform.split("/")[1]])

        # Add source and destination - preserve original repository name and tag for proper naming
        source_image = f"docker://{image_name}"

        # Parse image name to extract repository and tag
        if ':' in image_name:
            # Image name contains a tag (e.g., nginx:1.21 or registry/repo:tag)
            parts = image_name.split(':')
            if len(parts) == 2 and '/' not in parts[-1] and '.' not in parts[-1]:
                # Simple case: nginx:1.21 - last part is tag
                image_repo = parts[0]
                image_tag = parts[1]
            else:
                # Complex case: registry/namespace/repo:tag or no tag
                # Check if last part looks like a tag (no / and no .)
                if '/' not in parts[-1] and '.' not in parts[-1]:
                    image_repo = ':'.join(parts[:-1])
                    image_tag = parts[-1]
                else:
                    # No tag, just repository name
                    image_repo = image_name
                    image_tag = 'latest'
        else:
            # No tag specified, use 'latest'
            image_repo = image_name
            image_tag = 'latest'

        # Use the original repository name and tag for the archive to preserve naming
        dest_image = f"docker-archive:{final_output_path}:{image_repo}:{image_tag}"

        skopeo_cmd.extend([source_image, dest_image])

        logger.info(f"Running skopeo command: {' '.join(skopeo_cmd)}")

        # Run skopeo to download the image
        try:
            result = subprocess.run(skopeo_cmd, check=True, capture_output=True, text=True)
            logger.info(f"Skopeo output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            # Try without platform specification if specific platform fails
            if platform and platform.lower() != "all":
                logger.warning(f"Platform {platform} not found, trying default platform")
                fallback_cmd = ["skopeo", "copy", source_image, dest_image]
                result = subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)
                logger.info(f"Fallback skopeo output: {result.stdout}")
            else:
                raise Exception(f"Failed to download image with skopeo: {e.stderr}")

        # Get image details from the Docker archive file
        try:
            image_id = "unknown"
            image_size = 0

            if os.path.exists(final_output_path):
                # Get file size
                image_size = os.path.getsize(final_output_path)

                # Try to extract basic info from filename
                clean_image_name = image_name.replace(':', '_').replace('/', '_')
                image_id = f"sha256:{clean_image_name}"

        except Exception as e:
            logger.warning(f"Could not extract image details: {str(e)}")
            image_id = "unknown"
            image_size = 0

        logger.info(f"Image downloaded successfully. ID: {image_id}, Size: {image_size} bytes")

        # Export image based on format
        logger.info(f"Exporting image as {export_format} to: {final_output_path}")

        if export_format == "folder":
            # Extract Docker archive to folder using tar
            logger.info(f"Extracting Docker archive to folder: {final_output_path}")

            # Create directory for extraction
            Path(final_output_path).mkdir(parents=True, exist_ok=True)

            # Extract the tar file
            with tarfile.open(final_output_path, 'r') as tar:
                tar.extractall(path=final_output_path)

            logger.info(f"Image successfully extracted to folder: {final_output_path}")

            # Calculate total size of extracted folder
            export_size = 0
            for dirpath, _, filenames in os.walk(final_output_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        export_size += os.path.getsize(filepath)

        else:
            logger.info(f"Image successfully exported to tar file: {final_output_path}")
            export_size = image_size

        return {
            "export_path": final_output_path,
            "image_id": image_id,
            "image_size": export_size,
            "export_format": export_format
        }

    except subprocess.CalledProcessError as e:
        logger.error(f"Skopeo command failed: {e.stderr}")
        raise Exception(f"Failed to export Docker image with skopeo: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise Exception(f"Failed to export Docker image: {str(e)}")