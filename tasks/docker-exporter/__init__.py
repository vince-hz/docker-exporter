#region generated meta
import typing
from oocana import Context
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

import docker
import os
import logging
import tarfile
import tempfile
import shutil
from pathlib import Path

def main(params: Inputs, context: Context) -> Outputs:
    """
    Download Docker image with specific architecture and export as tar file or folder

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

        # Initialize Docker client with better error handling
        try:
            client = docker.from_env()
        except docker.errors.DockerException as e:
            if "Connection aborted" in str(e) or "No such file or directory" in str(e):
                raise Exception(
                    "Docker daemon is not running. Please start Docker service:\n"
                    "• On Linux/macOS: sudo systemctl start docker\n"
                    "• On Windows: Start Docker Desktop\n"
                    "• On macOS: Start Docker Desktop\n"
                    "If Docker is not installed, please install it first."
                )
            else:
                raise Exception(f"Failed to connect to Docker: {str(e)}")

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

        # Pull image with specific platform
        try:
            image = client.images.pull(image_name, platform=platform)
        except docker.errors.ImageNotFound:
            # Try without platform specification if specific platform fails
            logger.warning(f"Platform {platform} not found, trying default platform")
            image = client.images.pull(image_name)

        # Get image details
        image_id = image.id
        image_size = image.attrs.get('Size', 0)

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

        # Get the image object for export
        image_obj = client.images.get(image_id)

        if export_format == "folder":
            # Export to temporary tar file first, then extract
            with tempfile.NamedTemporaryFile(suffix='.tar', delete=False) as temp_tar:
                temp_tar_path = temp_tar.name

                # Export image to temporary tar file
                for chunk in image_obj.save():
                    temp_tar.write(chunk)

            # Extract tar file to output folder
            logger.info(f"Extracting tar file to folder: {final_output_path}")
            with tarfile.open(temp_tar_path, 'r') as tar:
                tar.extractall(final_output_path)

            # Clean up temporary tar file
            os.unlink(temp_tar_path)

            logger.info(f"Image successfully extracted to folder: {final_output_path}")

            # Calculate total size of extracted folder
            total_size = 0
            for dirpath, _, filenames in os.walk(final_output_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            export_size = total_size

        else:
            # Export to tar file (default behavior)
            with open(final_output_path, 'wb') as f:
                for chunk in image_obj.save():
                    f.write(chunk)

            logger.info(f"Image successfully exported to tar file: {final_output_path}")

            # Get file size of the tar file
            export_size = os.path.getsize(final_output_path)

        return {
            "export_path": final_output_path,
            "image_id": image_id,
            "image_size": export_size,
            "export_format": export_format
        }

    except docker.errors.DockerException as e:
        logger.error(f"Docker error occurred: {str(e)}")
        raise Exception(f"Docker operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise Exception(f"Failed to export Docker image: {str(e)}")
    finally:
        # Clean up Docker client
        try:
            client.close()
        except:
            pass