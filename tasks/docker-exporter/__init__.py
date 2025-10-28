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
import tempfile
import json
import shutil
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

        # Create temporary directory for skopeo operations
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_image_path = os.path.join(temp_dir, "temp_image")

            # Build skopeo command with platform override if specified
            skopeo_cmd = ["skopeo", "copy"]

            # Add platform override if specified
            if platform and platform.lower() != "all":
                skopeo_cmd.extend(["--override-os", platform.split("/")[0]])
                if "/" in platform:
                    skopeo_cmd.extend(["--override-arch", platform.split("/")[1]])

            # Add source and destination
            source_image = f"docker://{image_name}"
            dest_image = f"oci:{temp_image_path}"

            skopeo_cmd.extend([source_image, dest_image])

            logger.info(f"Running skopeo command: {' '.join(skopeo_cmd)}")

            # Run skopeo to download the image
            try:
                subprocess.run(skopeo_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                # Try without platform specification if specific platform fails
                if platform and platform.lower() != "all":
                    logger.warning(f"Platform {platform} not found, trying default platform")
                    fallback_cmd = ["skopeo", "copy", source_image, dest_image]
                    subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)
                else:
                    raise Exception(f"Failed to download image with skopeo: {e.stderr}")

            # Get image details from the OCI layout
            try:
                # Read the manifest to get image details
                manifest_path = os.path.join(temp_image_path, "blobs", "sha256")
                index_path = os.path.join(temp_image_path, "index.json")

                if os.path.exists(index_path):
                    with open(index_path, 'r') as f:
                        index_data = json.load(f)

                    # Get the first manifest digest
                    if index_data.get("manifests"):
                        manifest_digest = index_data["manifests"][0]["digest"]
                        manifest_file = os.path.join(manifest_path, manifest_digest.split(":")[1])

                        if os.path.exists(manifest_file):
                            with open(manifest_file, 'r') as f:
                                manifest_data = json.load(f)

                            # Extract image ID from config digest
                            if manifest_data.get("config"):
                                image_id = manifest_data["config"]["digest"]
                            else:
                                image_id = manifest_digest
                        else:
                            image_id = manifest_digest
                    else:
                        image_id = "unknown"
                else:
                    image_id = "unknown"

                # Calculate total size of downloaded image
                total_size = 0
                for root, dirs, files in os.walk(temp_image_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)

                image_size = total_size

            except Exception as e:
                logger.warning(f"Could not extract image details: {str(e)}")
                image_id = "unknown"
                image_size = 0

            logger.info(f"Image downloaded successfully. ID: {image_id}, Size: {image_size} bytes")

            # Ensure output directory exists
            if export_format == "folder":
                output_dir = final_output_path
            else:
                output_dir = os.path.dirname(final_output_path)

            if output_dir:
                Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Export image based on format
            logger.info(f"Exporting image as {export_format} to: {final_output_path}")

            if export_format == "folder":
                # Copy the OCI directory structure to output folder
                logger.info(f"Copying OCI image to folder: {final_output_path}")
                shutil.copytree(temp_image_path, final_output_path, dirs_exist_ok=True)

                logger.info(f"Image successfully copied to folder: {final_output_path}")

                # Calculate total size of copied folder
                export_size = 0
                for dirpath, _, filenames in os.walk(final_output_path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if os.path.exists(filepath):
                            export_size += os.path.getsize(filepath)

            else:
                # Create tar file from OCI directory
                logger.info(f"Creating tar file from OCI image: {final_output_path}")
                with tarfile.open(final_output_path, 'w') as tar:
                    tar.add(temp_image_path, arcname=os.path.basename(final_output_path).replace('.tar', ''))

                logger.info(f"Image successfully exported to tar file: {final_output_path}")

                # Get file size of the tar file
                export_size = os.path.getsize(final_output_path)

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